// Language translation functionality
const translations = {
  en: {
    "hero.title": "Easy Math Lang",
    "hero.subtitle": "Write math documents using simple text — no design skills needed.",
    "hero.buttons.download": "Download",
    "hero.buttons.github": "GitHub",
    "hero.buttons.docs": "Docs",
    "code_result.title": "Code → Result",
    "code_result.description": "Real ezmath examples compiled to show you exactly what you can write",
    "editor.title": "Editor Screenshots",
    "editor.description": "Screenshots from the real Easy Math Editor showing the interface with Vietnamese UI",
    "features.title": "Features",
    "features.items.symbol_bar.title": "Symbol Bar",
    "features.items.symbol_bar.desc": "Full Greek alphabet, arrows, relations and set/logic symbols",
    "features.items.draw_gallery.title": "*draw Gallery",
    "features.items.draw_gallery.desc": "28 geometry commands with thumbnails, syntax and descriptions",
    "features.items.lsp_diagnostics.title": "LSP Diagnostics",
    "features.items.lsp_diagnostics.desc": "Error checking with friendly hints and hover info",
    "features.items.vietnamese_ui.title": "Vietnamese UI",
    "features.items.vietnamese_ui.desc": "Vietnamese input methods supported via fcitx5 (Vietnamese Telex)",
    "features.items.auto_close_pairs.title": "Auto-close Pairs",
    "features.items.auto_close_pairs.desc": "Typing (, [, {, \" auto-inserts matching closer",
    "download.title": "Download",
    "download.description": "Get Easy Math Editor for your platform",
    "download.detect_os": "Detecting your OS...",
    "download.windows": "Windows",
    "download.macos": "macOS",
    "download.linux": "Linux",
    "docs.title": "Documentation",
    "docs.description": "All docs available on GitHub",
    "footer.license": "MIT License",
    "footer.github": "GitHub Repository",
    "language.en": "English",
    "language.vi": "Vietnamese",
    "common.and": "and",
    "common.or": "or",
    "common.not": "not",
    "common.for": "for",
    "common.from": "from",
    "common.to": "to",
    "common.in": "in",
    "common.on": "on",
    "common.with": "with",
    "common.of": "of",
    "common.the": "the",
    "common.a": "a",
    "common.an": "an",
    "common.this": "this",
    "common.that": "that"
  },
  vi: {
    "hero.title": "Easy Math Lang",
    "hero.subtitle": "Viết tài liệu toán học bằng văn bản đơn giản — không cần kỹ năng thiết kế.",
    "hero.buttons.download": "Tải xuống",
    "hero.buttons.github": "GitHub",
    "hero.buttons.docs": "Tài liệu",
    "code_result.title": "Code → Kết quả",
    "code_result.description": "Các ví dụ ezmath thực tế được biên dịch để cho bạn thấy chính xác những gì bạn có thể viết",
    "editor.title": "Ảnh chụp màn hình trình soạn thảo",
    "editor.description": "Các ảnh chụp màn hình từ Easy Math Editor thực sự hiển thị giao diện với UI tiếng Việt",
    "features.title": "Tính năng",
    "features.items.symbol_bar.title": "Thanh biểu tượng",
    "features.items.symbol_bar.desc": "Bảng chữ cái Hy Lạp đầy đủ, mũi tên, quan hệ và ký hiệu tập hợp/đại số học",
    "features.items.draw_gallery.title": "*draw Gallery",
    "features.items.draw_gallery.desc": "28 lệnh hình học với hình thu nhỏ, cú pháp và mô tả",
    "features.items.lsp_diagnostics.title": "Chẩn đoán LSP",
    "features.items.lsp_diagnostics.desc": "Kiểm tra lỗi với gợi ý thân thiện và thông tin hiển thị",
    "features.items.vietnamese_ui.title": "UI Tiếng Việt",
    "features.items.vietnamese_ui.desc": "Phương pháp nhập liệu tiếng Việt được hỗ trợ qua fcitx5 (Vietnamese Telex)",
    "features.items.auto_close_pairs.title": "Tự động đóng cặp",
    "features.items.auto_close_pairs.desc": "Nhập (, [, {, \" tự động chèn ký tự đóng khớp",
    "download.title": "Tải xuống",
    "download.description": "Tải Easy Math Editor cho nền tảng của bạn",
    "download.detect_os": "Đang phát hiện hệ điều hành của bạn...",
    "download.windows": "Windows",
    "download.macos": "macOS",
    "download.linux": "Linux",
    "docs.title": "Tài liệu",
    "docs.description": "Tất cả tài liệu có sẵn trên GitHub",
    "footer.license": "Giấy phép MIT",
    "footer.github": "Kho lưu trữ GitHub",
    "language.en": "English",
    "language.vi": "Tiếng Việt",
    "common.and": "và",
    "common.or": "hoặc",
    "common.not": "không",
    "common.for": "cho",
    "common.from": "từ",
    "common.to": "đến",
    "common.in": "trong",
    "common.on": "trên",
    "common.with": "với",
    "common.of": "của",
    "common.the": "cái",
    "common.a": "một",
    "common.an": "một",
    "common.this": "này",
    "common.that": "đó"
  }
};

let currentLang = 'en';

function translate() {
  const elements = document.querySelectorAll('[data-i18n]');
  
  elements.forEach(element => {
    const key = element.getAttribute('data-i18n');
    const translation = translations[currentLang][key];
    
    if (translation) {
      if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
        element.placeholder = translation;
      } else if (element.tagName === 'A' && element.getAttribute('data-i18n-attr')) {
        element.setAttribute(element.getAttribute('data-i18n-attr'), translation);
      } else {
        element.textContent = translation;
      }
    }
  });
  
  // Update language buttons
  document.querySelectorAll('.lang-btn').forEach(btn => {
    const lang = btn.getAttribute('data-lang');
    const textKey = `language.${lang}`;
    const text = translations[currentLang][textKey];
    
    if (text) {
      btn.textContent = text;
    }
  });
  
  // Update HTML lang attribute
  document.documentElement.lang = currentLang;
  
  // Save to localStorage
  try {
    localStorage.setItem('ezmath-language', currentLang);
  } catch (e) {
    // localStorage not available
  }
}

function setLanguage(lang) {
  currentLang = lang;
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-lang') === lang);
  });
  translate();
}

function detectOS() {
  const platformLinks = document.querySelectorAll('.platform-link');
  const userAgent = navigator.userAgent;
  
  let detectedPlatform = null;
  
  if (/Win/.test(userAgent)) {
    detectedPlatform = 'windows';
  } else if (/Mac/.test(userAgent)) {
    detectedPlatform = 'macos';
  } else if (/Linux/.test(userAgent)) {
    detectedPlatform = 'linux';
  }
  
  platformLinks.forEach(link => {
    link.classList.toggle('active-platform', link.getAttribute('data-platform') === detectedPlatform);
  });
}

function init() {
  // Check for saved language preference
  try {
    const savedLang = localStorage.getItem('ezmath-language');
    if (savedLang && ['en', 'vi'].includes(savedLang)) {
      currentLang = savedLang;
    } else {
      // Auto-detect from browser language
      const browserLang = navigator.language || navigator.userLanguage;
      if (browserLang.startsWith('vi')) {
        currentLang = 'vi';
      }
    }
  } catch (e) {
    // localStorage not available or error
  }
  
  // Apply initial language
  setLanguage(currentLang);
  
  // Detect OS
  detectOS();
  
  // Theme toggle
  const themeToggle = document.getElementById('theme-toggle');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  
  // Check for saved theme preference
  const savedTheme = localStorage.getItem('ezmath-theme');
  if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
    document.body.classList.add('dark-mode');
  }
  
  themeToggle.addEventListener('click', () => {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');
    try {
      localStorage.setItem('ezmath-theme', isDark ? 'dark' : 'light');
    } catch (e) {
      // localStorage not available
    }
  });
  
  // Language switch
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const lang = btn.getAttribute('data-lang');
      setLanguage(lang);
    });
  });
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

// Add 'active-platform' class to initially detected OS
window.addEventListener('load', detectOS);