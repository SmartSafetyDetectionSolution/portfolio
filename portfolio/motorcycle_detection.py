import cv2
from ultralytics import YOLO
import os

def main():
    # 1. YOLO 모델 불러오기
    model_path = r'C:\test\yolo11n.pt'
    if os.path.exists(model_path):
        model = YOLO(model_path)
    else:
        model = YOLO('yolov8n.pt')

    # 2. 제공된 highway.mp4 파일을 읽기
    video_path = r'C:\test\data\highway.mp4'
    if not os.path.exists(video_path):
        print(f"오류: '{video_path}' 파일을 찾을 수 없습니다.")
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"오류: 동영상 파일을 열 수 없습니다.")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0:
        fps = 30.0
    
    frame_count = 0
    first_detected_time = None
    
    print("탐지를 시작합니다. 'q'를 누르면 종료됩니다.")

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break

        pure_frame = frame.copy()
        box_only_frame = frame.copy()

        results = model(frame, classes=[3], verbose=False)
        
        motorcycle_found_in_frame = False
        for result in results:
            if len(result.boxes) > 0:
                motorcycle_found_in_frame = True
                break

        if motorcycle_found_in_frame:
            current_time = frame_count / fps
            
            for result in results:
                for box in result.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = box.conf[0]
                    # 평가5용 화면에만 박스 그리기
                    cv2.rectangle(box_only_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(box_only_frame, f"motorcycle {conf:.2f}", (x1, y1 - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    
                    # 실시간 창용 화면에 박스 그리기
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"motorcycle {conf:.2f}", (x1, y1 - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            cv2.putText(frame, "Motorcycle Detected", (40, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
            cv2.putText(frame, f"Detect Time: {current_time:.2f}s", (frame.shape[1] - 350, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 2)

            if first_detected_time is None:
                first_detected_time = current_time
                try:
                    with open(r'C:\test\motorcycle_result.txt', 'w', encoding='utf-8') as f:
                        f.write(f"{first_detected_time:.2f}")
                    
                    cv2.imwrite(r'C:\test\motorcycle_evaluation4.jpg', pure_frame)
                    cv2.imwrite(r'C:\test\motorcycle_evaluation5.jpg', box_only_frame)
                    
                    print(f"탐지 성공: {first_detected_time:.2f}초 (평가별 캡처 완료)")
                except Exception as e:
                    print(f"파일 저장 중 오류 발생: {e}")

        cv2.imshow('Motorcycle Detection', frame)
        frame_count += 1
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
