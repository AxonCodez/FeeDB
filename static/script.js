document.addEventListener('DOMContentLoaded', function() {
    // Add any interactive features here
    console.log('FeeDB School System Loaded');
    
    // Auto-logout after 30 minutes of inactivity
    let timeout;
    
    function resetTimeout() {
        clearTimeout(timeout);
        timeout = setTimeout(function() {
            if (window.location.pathname !== '/login') {
                alert('Session expired. Please login again.');
                window.location.href = '/logout';
            }
        }, 30 * 60 * 1000); // 30 minutes
    }
    
    // Reset timeout on user activity
    document.addEventListener('mousedown', resetTimeout);
    document.addEventListener('mousemove', resetTimeout);
    document.addEventListener('keypress', resetTimeout);
    document.addEventListener('scroll', resetTimeout);
    document.addEventListener('touchstart', resetTimeout);
    
    // Initialize timeout
    resetTimeout();
});