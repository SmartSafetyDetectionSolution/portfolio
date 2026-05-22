import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from PIL import Image
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
CAPTURE_DIR = BASE_DIR / "static" / "safety" / "captures"
ULTRALYTICS_DIR = DATA_DIR / "ultralytics"
CONFIG_PATH = DATA_DIR / "safety_monitor_config.json"
ALERT_LOG_PATH = DATA_DIR / "safety_alert_log.jsonl"

from .db_service import ensure_default_admin, import_alerts_from_jsonl, insert_alert, list_alerts as list_alerts_from_db


# 기본 안전모 색상 범위를 미리 준비해 두면 별도 학습 모델이 없어도 보조 판단이 가능합니다.
DEFAULT_HELMET_HSV_RANGES: List[Dict[str, Any]] = [
    {"label": "yellow", "lower": [15, 70, 80], "upper": [40, 255, 255]},
    {"label": "orange", "lower": [5, 90, 80], "upper": [18, 255, 255]},
    {"label": "white", "lower": [0, 0, 180], "upper": [180, 55, 255]},
    {"label": "blue", "lower": [95, 80, 70], "upper": [125, 255, 255]},
    {"label": "red-low", "lower": [0, 90, 70], "upper": [10, 255, 255]},
    {"label": "red-high", "lower": [170, 90, 70], "upper": [180, 255, 255]},
]


# 업체마다 개별 카메라와 감지 기준을 저장하기 위한 기본 모니터링 설정입니다.
DEFAULT_MONITOR_CONFIG: Dict[str, Any] = {
    "camera_mode": "browser",
    "camera_source": "0",
    # 4분할(슬롯)용 카메라 소스 목록입니다. 없으면 camera_source 값을 4개로 복제합니다.
    "camera_sources": ["0", "0", "0", "0"],
    # OpenCV 4분할 표시 방식
    # - snapshot: 스냅샷(JPEG) 폴링으로 가볍게 표시 (RPi 권장)
    # - mjpeg: MJPEG 스트림 4개로 실시간 표시 (PC 권장)
    "display_mode": "snapshot",
    "display_fps": 5,
    # 분석 방식
    # - round_robin: 슬롯별 순차 분석(부하 감소)
    # - all: 매 주기 4슬롯 모두 분석(부하 증가)
    "analysis_mode": "round_robin",
    "frame_interval_ms": 1500,
    "helmet_min_ratio": 0.08,
    "shoe_dark_ratio": 0.18,
    "shoe_value_max": 110,
    "alert_cooldown_seconds": 8,
    "yolo_model_path": "yolov8n.pt",
    "yolo_confidence": 0.35,
    "helmet_hsv_ranges": DEFAULT_HELMET_HSV_RANGES,
    # 경고 캡처를 다른 컴퓨터로 전송할 때 사용합니다.
    "remote_capture_enabled": False,
    "remote_capture_url": "",
    "remote_capture_api_key": "change-me",
}


# 초기 앱은 한 개 업체를 포함한 상태로 시작하고, 이후 관리자에서 업체를 계속 추가할 수 있습니다.
DEFAULT_CONFIG: Dict[str, Any] = {
    "admin": {
        "username": "admin",
        "password_hash": generate_password_hash("admin1234!"),
    },
    "email": {
        "dev_mode": True,
        "smtp_host": "",
        "smtp_port": 587,
        "smtp_user": "",
        "smtp_password": "",
        "use_tls": True,
        "sender": "",
    },
    "active_company_id": "default-company",
    "companies": [
        {
            "id": "default-company",
            "company_name": "기본 업체",
            "site_name": "기본 현장",
            "manager_name": "현장 관리자",
            "monitor": DEFAULT_MONITOR_CONFIG,
        }
    ],
}


# 앱 실행에 필요한 데이터 폴더와 기본 설정 파일을 준비합니다.
def ensure_runtime_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    ULTRALYTICS_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_PATH.exists():
        save_app_config(DEFAULT_CONFIG)

    if not ALERT_LOG_PATH.exists():
        ALERT_LOG_PATH.write_text("", encoding="utf-8")

    # 사용자(회원) 테이블이 비어 있으면 기본 관리자 계정을 DB에 심습니다.
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else DEFAULT_CONFIG
        admin = config.get("admin", DEFAULT_CONFIG["admin"])
        ensure_default_admin(str(admin.get("username", "admin")), str(admin.get("password_hash", "")))
    except Exception:
        pass

    # 과거 JSONL 기반 경고 로그가 있다면 SQLite DB로 옮겨 이후 조회를 빠르게 합니다.
    try:
        # DB가 비어 있는 경우에만 이관합니다.
        if ALERT_LOG_PATH.exists():
            existing = list_alerts_from_db(limit=1)
            if not existing:
                import_alerts_from_jsonl(ALERT_LOG_PATH)
    except Exception:
        # 이관 실패는 치명적이지 않으므로 무시하고 계속 실행합니다.
        pass


# 업체 ID에 사용할 안전한 슬러그를 만듭니다.
def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9가-힣]+", "-", (text or "").strip().lower())
    cleaned = cleaned.strip("-")
    return cleaned or "company"


# 딕셔너리 깊은 복사를 위해 JSON 직렬화를 사용합니다.
def _clone_json(data: Any) -> Any:
    return json.loads(json.dumps(data, ensure_ascii=False))


# 저장된 업체 설정이 부족하더라도 기본값을 채워 안정적으로 사용합니다.
def _normalize_company(company_data: Dict[str, Any], index: int = 0) -> Dict[str, Any]:
    normalized_monitor = _clone_json(DEFAULT_MONITOR_CONFIG)
    normalized_monitor.update(company_data.get("monitor", {}))

    # camera_sources가 없다면 기존 camera_source를 4개로 복제해 호환성을 유지합니다.
    camera_source_text = str(normalized_monitor.get("camera_source", "0")).strip() or "0"
    sources = normalized_monitor.get("camera_sources")
    if not isinstance(sources, list) or len(sources) != 4:
        sources = [camera_source_text, camera_source_text, camera_source_text, camera_source_text]
    sources = [(str(item).strip() or camera_source_text) for item in sources[:4]]
    normalized_monitor["camera_sources"] = sources
    normalized_monitor["camera_source"] = camera_source_text

    display_mode = str(normalized_monitor.get("display_mode", "snapshot")).strip().lower()
    if display_mode not in {"snapshot", "mjpeg"}:
        display_mode = "snapshot"
    normalized_monitor["display_mode"] = display_mode

    try:
        display_fps = int(normalized_monitor.get("display_fps", 5))
    except (TypeError, ValueError):
        display_fps = 5
    normalized_monitor["display_fps"] = max(1, min(15, display_fps))

    analysis_mode = str(normalized_monitor.get("analysis_mode", "round_robin")).strip().lower()
    if analysis_mode not in {"round_robin", "all"}:
        analysis_mode = "round_robin"
    normalized_monitor["analysis_mode"] = analysis_mode

    company_name = str(company_data.get("company_name", "")).strip() or f"업체 {index + 1}"
    site_name = str(company_data.get("site_name", "")).strip() or f"{company_name} 현장"
    manager_name = str(company_data.get("manager_name", "")).strip() or "현장 관리자"
    company_id = str(company_data.get("id", "")).strip() or f"{_slugify(company_name)}-{index + 1}"

    return {
        "id": company_id,
        "company_name": company_name,
        "site_name": site_name,
        "manager_name": manager_name,
        "monitor": normalized_monitor,
    }


# 과거 단일 monitor 구조를 새로운 companies 구조로 자동 이전합니다.
def _migrate_legacy_config(loaded_config: Dict[str, Any]) -> Dict[str, Any]:
    if loaded_config.get("companies"):
        return loaded_config

    legacy_monitor = loaded_config.get("monitor", {})
    default_company = _normalize_company(
        {
            "id": loaded_config.get("active_company_id", "default-company"),
            "company_name": "기본 업체",
            "site_name": "기본 현장",
            "manager_name": "현장 관리자",
            "monitor": legacy_monitor,
        }
    )

    return {
        "admin": loaded_config.get("admin", {}),
        "active_company_id": default_company["id"],
        "companies": [default_company],
    }


# 저장된 설정을 읽고 여러 업체가 사용할 수 있는 공통 구조로 맞춥니다.
def load_app_config() -> Dict[str, Any]:
    ensure_runtime_files()
    loaded_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    loaded_config = _migrate_legacy_config(loaded_config)

    merged_config = _clone_json(DEFAULT_CONFIG)
    merged_config["admin"].update(loaded_config.get("admin", {}))
    merged_config["email"].update(loaded_config.get("email", {}))

    companies = loaded_config.get("companies", [])
    if not companies:
        companies = merged_config["companies"]

    merged_config["companies"] = [_normalize_company(company, index) for index, company in enumerate(companies)]
    valid_company_ids = {company["id"] for company in merged_config["companies"]}

    active_company_id = str(loaded_config.get("active_company_id", "")).strip()
    if active_company_id not in valid_company_ids:
        active_company_id = merged_config["companies"][0]["id"]
    merged_config["active_company_id"] = active_company_id

    return merged_config


# 설정을 저장하기 전에 구조를 표준화하여 UTF-8로 안전하게 기록합니다.
def save_app_config(app_config: Dict[str, Any]) -> None:
    ensure_runtime_files()
    normalized_config = load_app_config()
    normalized_config["admin"].update(app_config.get("admin", {}))

    companies = app_config.get("companies", normalized_config["companies"])
    normalized_config["companies"] = [_normalize_company(company, index) for index, company in enumerate(companies)]

    valid_company_ids = {company["id"] for company in normalized_config["companies"]}
    active_company_id = str(app_config.get("active_company_id", normalized_config["active_company_id"])).strip()
    if active_company_id not in valid_company_ids:
        active_company_id = normalized_config["companies"][0]["id"]
    normalized_config["active_company_id"] = active_company_id

    CONFIG_PATH.write_text(json.dumps(normalized_config, ensure_ascii=False, indent=2), encoding="utf-8")


# 저장된 해시와 평문 비밀번호를 비교할 때 werkzeug의 보안 해시 검증 함수를 사용합니다.
def verify_password(password_hash: str, plain_password: str) -> bool:
    return check_password_hash(password_hash, plain_password)


# 관리자 계정명과 비밀번호를 바꿀 수 있도록 설정 객체를 수정합니다.
def update_admin_credentials(app_config: Dict[str, Any], username: str, password: str) -> None:
    app_config["admin"]["username"] = username
    if password:
        app_config["admin"]["password_hash"] = generate_password_hash(password)


# 현재 활성 업체를 찾아 모니터링과 관리자 화면에서 공통으로 사용합니다.
def get_active_company(app_config: Dict[str, Any]) -> Dict[str, Any]:
    active_company_id = app_config.get("active_company_id")
    for company in app_config.get("companies", []):
        if company["id"] == active_company_id:
            return company
    return app_config["companies"][0]


# 활성 업체의 모니터링 설정만 바로 쓸 수 있게 분리합니다.
def get_active_monitor_config(app_config: Dict[str, Any]) -> Dict[str, Any]:
    return get_active_company(app_config)["monitor"]


# 새 업체를 추가할 때 중복되지 않는 ID를 생성합니다.
def add_company(app_config: Dict[str, Any], company_name: str, site_name: str, manager_name: str) -> Dict[str, Any]:
    base_slug = _slugify(company_name)
    existing_ids = {company["id"] for company in app_config.get("companies", [])}
    candidate_id = base_slug
    suffix = 1

    while candidate_id in existing_ids:
        suffix += 1
        candidate_id = f"{base_slug}-{suffix}"

    company = _normalize_company(
        {
            "id": candidate_id,
            "company_name": company_name,
            "site_name": site_name,
            "manager_name": manager_name,
            "monitor": DEFAULT_MONITOR_CONFIG,
        },
        len(app_config.get("companies", [])),
    )
    app_config.setdefault("companies", []).append(company)
    app_config["active_company_id"] = company["id"]
    return company


# 활성 업체를 바꿔 여러 업체가 한 시스템을 함께 쓰도록 지원합니다.
def set_active_company(app_config: Dict[str, Any], company_id: str) -> bool:
    target_id = str(company_id or "").strip()
    for company in app_config.get("companies", []):
        if company["id"] == target_id:
            app_config["active_company_id"] = target_id
            return True
    return False


# 경고 이미지를 저장하고 나중에 관리자 화면에서 볼 수 있도록 로그도 남깁니다.
def save_alert_capture(frame_bgr: np.ndarray, detection_result: Dict[str, Any], source_label: str) -> Dict[str, Any]:
    ensure_runtime_files()
    image = Image.fromarray(frame_bgr[:, :, ::-1])
    timestamp_text = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    file_name = f"alert_{timestamp_text}.png"
    file_path = CAPTURE_DIR / file_name
    image.save(file_path, format="PNG")

    log_item = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_label": source_label,
        "file_name": file_name,
        "relative_path": f"static/safety/captures/{file_name}",
        "helmet_detected": bool(detection_result.get("helmet_detected")),
        "shoes_detected": bool(detection_result.get("shoes_detected")),
        "alert_reason": detection_result.get("alert_message") or detection_result.get("message", "경고"),
        "helmet_ratio": round(float(detection_result.get("helmet_ratio", 0.0)), 4),
        "shoe_dark_ratio": round(float(detection_result.get("shoe_dark_ratio", 0.0)), 4),
        "detector_summary": detection_result.get("detector_summary", "감지 정보 없음"),
    }

    with ALERT_LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(log_item, ensure_ascii=False) + "\n")

    # 동일한 데이터를 SQLite에도 저장해 검색/정렬을 빠르게 합니다.
    try:
        insert_alert(log_item)
    except Exception:
        pass

    return log_item


# 캡처 파일명을 실제 경로로 변환합니다.
def resolve_capture_path(file_name: str) -> Path:
    return (CAPTURE_DIR / str(file_name)).resolve()


# 관리자 화면에서 최신 경고를 먼저 볼 수 있도록 최근 로그부터 반환합니다.
def list_alerts(limit: int = 30) -> List[Dict[str, Any]]:
    ensure_runtime_files()
    try:
        return list_alerts_from_db(limit=limit)
    except Exception:
        lines = ALERT_LOG_PATH.read_text(encoding="utf-8").splitlines()
        parsed_items = []
        for line in reversed(lines):
            if not line.strip():
                continue
            parsed_items.append(json.loads(line))
            if len(parsed_items) >= limit:
                break
        return parsed_items
