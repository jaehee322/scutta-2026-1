function verifyPassword() {
    const correctPassword = "yeong6701";
    const inputPassword = document.getElementById('password-input').value;
    const errorMessage = document.getElementById('error-message');

    if (inputPassword === correctPassword) {
        window.location.href = '/betting_approval';
    } else {
        errorMessage.classList.remove('hidden');
    }
}

function handleKeyPress(event) {
    if (event.key === 'Enter') {
        verifyPassword();
    }
}