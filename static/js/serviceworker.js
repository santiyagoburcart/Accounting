self.addEventListener('install', function(event) {
    console.log('Service Worker installing.');
});

self.addEventListener('fetch', function(event) {
    // فعلاً استراتژی خاصی برای آفلاین نداریم
});