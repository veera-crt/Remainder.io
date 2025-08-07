document.addEventListener('DOMContentLoaded', function() {
    const sendOtpBtn = document.getElementById('sendOtpBtn');
    const verifyOtpBtn = document.getElementById('verifyOtpBtn');
    const newReminderBtn = document.getElementById('newReminderBtn');
    const step1 = document.getElementById('step1');
    const step2 = document.getElementById('step2');
    const success = document.getElementById('success');
    const otpStatus = document.getElementById('otpStatus');

    sendOtpBtn.addEventListener('click', sendOtp);
    verifyOtpBtn.addEventListener('click', verifyOtp);
    newReminderBtn.addEventListener('click', resetForm);

    function sendOtp() {
        const receiverEmail = document.getElementById('receiver_email').value;
        const reminderMessage = document.getElementById('reminder_message').value;
        const reminderTime = document.getElementById('reminder_time').value;

        if (!receiverEmail || !reminderMessage || !reminderTime) {
            alert('Please fill in all fields');
            return;
        }

        sendOtpBtn.disabled = true;
        sendOtpBtn.textContent = 'Sending OTP...';

        fetch('http://localhost:5000/send_otp', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                receiver_email: receiverEmail,
                reminder_message: reminderMessage,
                reminder_time: reminderTime
            })
        })
        .then(async response => {
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Failed to send OTP');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                step1.style.display = 'none';
                step2.style.display = 'block';
                otpStatus.textContent = '';
            } else {
                throw new Error(data.message || 'Unknown error');
            }
        })
        .catch(error => {
            alert('Error: ' + error.message);
            console.error('Error:', error);
        })
        .finally(() => {
            sendOtpBtn.disabled = false;
            sendOtpBtn.textContent = 'Send OTP';
        });
    }

    function verifyOtp() {
        const otp = document.getElementById('otp').value;
        const receiverEmail = document.getElementById('receiver_email').value;
        const reminderMessage = document.getElementById('reminder_message').value;
        const reminderTime = document.getElementById('reminder_time').value;

        if (!otp || otp.length !== 6) {
            alert('Please enter a valid 6-digit OTP');
            return;
        }

        verifyOtpBtn.disabled = true;
        verifyOtpBtn.textContent = 'Verifying...';

        fetch('http://localhost:5000/verify_otp', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                receiver_email: receiverEmail,
                reminder_message: reminderMessage,
                reminder_time: reminderTime,
                otp: otp
            })
        })
        .then(async response => {
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Verification failed');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // Update success message to show "Thank You"
                const successTitle = success.querySelector('h2');
                const successMessage = success.querySelector('p');
                
                successTitle.textContent = 'Thank You!';
                successMessage.textContent = 'Your reminder has been successfully scheduled.';
                
                step2.style.display = 'none';
                success.style.display = 'block';
            } else {
                throw new Error(data.message || 'Invalid OTP');
            }
        })
        .catch(error => {
            otpStatus.textContent = error.message;
            otpStatus.style.color = 'red';
            console.error('Error:', error);
        })
        .finally(() => {
            verifyOtpBtn.disabled = false;
            verifyOtpBtn.textContent = 'Verify & Schedule Reminder';
        });
    }

    function resetForm() {
        document.getElementById('receiver_email').value = '';
        document.getElementById('reminder_message').value = '';
        document.getElementById('reminder_time').value = '';
        document.getElementById('otp').value = '';
        otpStatus.textContent = '';
        
        success.style.display = 'none';
        step2.style.display = 'none';
        step1.style.display = 'block';
        
        // Reset success message to original for next use
        const successTitle = success.querySelector('h2');
        const successMessage = success.querySelector('p');
        successTitle.textContent = 'Reminder Scheduled Successfully!';
        successMessage.textContent = 'Your reminder has been verified and scheduled.';
    }
});