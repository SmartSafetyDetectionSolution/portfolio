// ===== Global Functionality =====

document.addEventListener('DOMContentLoaded', () => {
    // 1. Navigation Scroll Effect
    const navbar = document.querySelector('.navbar');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });

    // 2. Mobile Menu Toggle
    const menuBtn = document.getElementById('menuBtn');
    const navLinks = document.getElementById('navLinks');
    if (menuBtn) {
        menuBtn.addEventListener('click', () => {
            navLinks.classList.toggle('active');
        });
    }

    // 3. Theme Toggle
    const themeToggle = document.getElementById('themeToggle');
    const body = document.body;
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', newTheme);
            document.body.setAttribute('data-theme', newTheme);
            themeToggle.textContent = newTheme === 'light' ? '🌙' : '☀️';
            localStorage.setItem('theme', newTheme);
        });
    }

    // 4. Project Modal Logic (상세보기 버튼 작동)
    const modal = document.getElementById('projectModal');
    const modalClose = document.getElementById('modalClose');
    const detailButtons = document.querySelectorAll('.btn-detail');

    if (modal) {
        detailButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                // 데이터 채우기
                document.getElementById('modalTitle').textContent = btn.dataset.title;
                document.getElementById('modalDescription').textContent = btn.dataset.description;
                
                const features = JSON.parse(btn.dataset.features || '[]');
                const featuresContainer = document.getElementById('modalFeatures');
                featuresContainer.innerHTML = features.map(f => `<div class="feature-item"><div class="feature-title">${f}</div></div>`).join('');
                
                modal.classList.add('active');
                document.body.style.overflow = 'hidden'; // 스크롤 방지
            });
        });

        modalClose.addEventListener('click', () => {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        });

        window.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
                document.body.style.overflow = '';
            }
        });
    }

    // 5. Experience Lightbox Logic (현장 사진 보기)
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.querySelector('.lightbox-img');
    const lightboxCaption = document.querySelector('.lightbox-caption');
    const lightboxClose = document.querySelector('.lightbox-close');
    const expThumbs = document.querySelectorAll('.exp-thumb');

    if (lightbox) {
        expThumbs.forEach(thumb => {
            thumb.addEventListener('click', () => {
                const img = thumb.querySelector('img');
                const caption = thumb.getAttribute('data-caption');
                
                lightboxImg.src = img.src;
                lightboxCaption.textContent = caption;
                lightbox.classList.add('active');
                document.body.style.overflow = 'hidden';
            });
        });

        lightboxClose.addEventListener('click', () => {
            lightbox.classList.remove('active');
            document.body.style.overflow = '';
        });

        lightbox.addEventListener('click', (e) => {
            if (e.target === lightbox) {
                lightbox.classList.remove('active');
                document.body.style.overflow = '';
            }
        });
    }

    // 6. Typewriter Animation (Super Stable Version)

    // 7. Scroll Animation (IntersectionObserver)
    const observerOptions = {
        threshold: 0.1,
        rootMargin: "0px 0px -50px 0px"
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-in');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    const animateElements = document.querySelectorAll('.animate-on-scroll');
    animateElements.forEach(el => observer.observe(el));

});

// ===== Typewriter Class =====
class TypeWriter {
    constructor(element, words, wait = 3000) {
        this.element = element;
        this.words = words;
        this.txt = '';
        this.wordIndex = 0;
        this.wait = wait;
        this.isDeleting = false;
        this.tick();
    }

    tick() {
        const i = this.wordIndex % this.words.length;
        const fullTxt = this.words[i];

        if (this.isDeleting) {
            this.txt = fullTxt.substring(0, this.txt.length - 1);
        } else {
            this.txt = fullTxt.substring(0, this.txt.length + 1);
        }

        this.element.textContent = this.txt;

        let typeSpeed = 150;
        if (this.isDeleting) typeSpeed /= 2;

        if (!this.isDeleting && this.txt === fullTxt) {
            typeSpeed = this.wait;
            this.isDeleting = true;
        } else if (this.isDeleting && this.txt === '') {
            this.isDeleting = false;
            this.wordIndex++;
            typeSpeed = 500;
        }

        setTimeout(() => this.tick(), typeSpeed);
    }
}
