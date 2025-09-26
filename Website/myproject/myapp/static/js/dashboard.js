// Dashboard initialization
document.addEventListener('DOMContentLoaded', function() {
    initializeSidebar();
    initializeCharts();
    initializeDataTables();
    initializeFilters();
    setupEventListeners();
});

// Sidebar functionality
function initializeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const content = document.getElementById('content');
    const sidebarCollapse = document.getElementById('sidebarCollapse');

    if (sidebarCollapse) {
        sidebarCollapse.addEventListener('click', () => {
            sidebar.classList.toggle('active');
            content.classList.toggle('active');
            localStorage.setItem('sidebarState', sidebar.classList.contains('active'));
        });
    }

    // Restore sidebar state
    const sidebarState = localStorage.getItem('sidebarState');
    if (sidebarState === 'true') {
        sidebar.classList.add('active');
        content.classList.add('active');
    }
}

// Charts initialization
function initializeCharts() {
    // User Growth Chart
    const userGrowthChart = document.getElementById('userGrowthChart');
    if (userGrowthChart) {
        new Chart(userGrowthChart, {
            type: 'line',
            data: {
                labels: chartData.labels,
                datasets: [{
                    label: 'User Growth',
                    data: chartData.userGrowth,
                    borderColor: '#3498db',
                    tension: 0.4,
                    fill: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                    }
                }
            }
        });
    }

    // Payment Trends Chart
    const paymentTrendsChart = document.getElementById('paymentTrendsChart');
    if (paymentTrendsChart) {
        new Chart(paymentTrendsChart, {
            type: 'bar',
            data: {
                labels: chartData.labels,
                datasets: [{
                    label: 'Payment Trends',
                    data: chartData.paymentTrends,
                    backgroundColor: '#2ecc71'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    }

    // Membership Distribution Chart
    const membershipChart = document.getElementById('membershipChart');
    if (membershipChart) {
        new Chart(membershipChart, {
            type: 'doughnut',
            data: {
                labels: ['Regular', 'VIP', 'Diamond'],
                datasets: [{
                    data: chartData.membershipDistribution,
                    backgroundColor: ['#95a5a6', '#f1c40f', '#9b59b6']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    }
}

// DataTables initialization
function initializeDataTables() {
    $('.data-table').DataTable({
        pageLength: 10,
        responsive: true,
        dom: '<"filters-toolbar"f>rt<"bottom"lip>',
        language: {
            search: "_INPUT_",
            searchPlaceholder: "Search..."
        }
    });
}

// Filter functionality
function initializeFilters() {
    // Date range picker
    $('.date-range-picker').daterangepicker({
        ranges: {
            'Today': [moment(), moment()],
            'Yesterday': [moment().subtract(1, 'days'), moment().subtract(1, 'days')],
            'Last 7 Days': [moment().subtract(6, 'days'), moment()],
            'Last 30 Days': [moment().subtract(29, 'days'), moment()],
            'This Month': [moment().startOf('month'), moment().endOf('month')],
            'Last Month': [moment().subtract(1, 'month').startOf('month'), moment().subtract(1, 'month').endOf('month')]
        },
        alwaysShowCalendars: true,
        startDate: moment().subtract(29, 'days'),
        endDate: moment()
    });

    // Status filter
    $('.status-filter').on('change', function() {
        const table = $(this).closest('.card').find('.data-table').DataTable();
        table.column($(this).data('column')).search(this.value).draw();
    });
}

// User Management Functions
function updateUserStatus(userId, action) {
    const url = action === 'activate' ? '/api/user/activate/' : '/api/user/deactivate/';
    
    fetch(`${url}${userId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('success', `User successfully ${action}d`);
            updateUserRow(userId, data);
        } else {
            showNotification('error', data.message);
        }
    })
    .catch(error => {
        showNotification('error', 'An error occurred while updating user status');
        console.error('Error:', error);
    });
}

// Video Management Functions
function handleVideoUpload(event) {
    const file = event.target.files[0];
    const formData = new FormData();
    formData.append('video', file);
    formData.append('tier', document.getElementById('videoTier').value);

    fetch('/api/videos/upload/', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('success', 'Video uploaded successfully');
            refreshVideoList();
        } else {
            showNotification('error', data.message);
        }
    })
    .catch(error => {
        showNotification('error', 'Error uploading video');
        console.error('Error:', error);
    });
}

// Payment Management Functions
function handlePayment(paymentId, action, feedback = '') {
    fetch('/api/payments/handle/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            paymentId: paymentId,
            action: action,
            feedback: feedback
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('success', `Payment ${action}d successfully`);
            refreshPaymentList();
        } else {
            showNotification('error', data.message);
        }
    })
    .catch(error => {
        showNotification('error', 'Error processing payment');
        console.error('Error:', error);
    });
}

// Utility Functions
function showNotification(type, message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.getElementById('alert-container').appendChild(alertDiv);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Event Listeners
function setupEventListeners() {
    // Bulk actions
    document.querySelector('.bulk-action-btn')?.addEventListener('click', function() {
        const selectedIds = Array.from(document.querySelectorAll('.user-checkbox:checked'))
            .map(checkbox => checkbox.value);
        
        if (selectedIds.length === 0) {
            showNotification('warning', 'Please select at least one user');
            return;
        }

        const action = document.querySelector('.bulk-action-select').value;
        handleBulkAction(selectedIds, action);
    });

    // Video upload
    document.querySelector('#videoUpload')?.addEventListener('change', handleVideoUpload);

    // Payment proof modal
    document.querySelectorAll('.view-payment-proof')?.forEach(button => {
        button.addEventListener('click', function() {
            const paymentId = this.dataset.paymentId;
            showPaymentProofModal(paymentId);
        });
    });
}

// Initialize tooltips and popovers
$(function () {
    $('[data-toggle="tooltip"]').tooltip();
    $('[data-toggle="popover"]').popover();
});
