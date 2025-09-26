// Store the folder ID to be deleted
let folderToDelete = null;

// Handle delete button click
$('.delete-folder').click(function() {
    folderToDelete = $(this).data('folder-id');
    $('#deleteFolderModal').modal('show');
});

// Handle confirm delete
$('#confirmDelete').click(function() {
    if (!folderToDelete) return;

    const $folderRow = $(`.folder-row[data-folder-id="${folderToDelete}"]`);
    const $deleteButton = $(this);
    
    // Disable the button and show loading state
    $deleteButton.prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> Deleting...');

    $.ajax({
        url: `/drive/folders/${folderToDelete}/delete/`,
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken()
        },
        success: function(response) {
            // Hide the modal
            $('#deleteFolderModal').modal('hide');
            
            // Remove the folder row with animation
            $folderRow.fadeOut(400, function() {
                $(this).remove();
            });
            
            // Show success message
            showAlert('success', 'Folder deleted successfully');
        },
        error: function(xhr) {
            // Show error message
            const errorMsg = xhr.responseJSON?.message || 'Failed to delete folder. Please try again.';
            showAlert('error', errorMsg);
        },
        complete: function() {
            // Reset button state
            $deleteButton.prop('disabled', false).html('Delete');
            folderToDelete = null;
        }
    });
});

// Helper function to show alerts
function showAlert(type, message) {
    const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
    const $alert = $(`
        <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="close" data-dismiss="alert">
                <span>&times;</span>
            </button>
        </div>
    `);
    
    $('#alertContainer').append($alert);
    setTimeout(() => $alert.alert('close'), 5000);
}

// Folder Management Functions
function showAddFolderModal() {
    document.getElementById('folderModal').style.display = 'block';
}

function closeModal() {
    document.getElementById('folderModal').style.display = 'none';
}

function viewFolder(folderId) {
    window.location.href = `/admin/drive-folder/${folderId}/videos/`;
}

// Real-time folder updates
let eventSource;

function setupRealtimeUpdates() {
    // Close existing connection if any
    if (eventSource) {
        eventSource.close();
    }

    // Create new EventSource connection
    eventSource = new EventSource('/admin/drive-folders/events/');
    
    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        updateFolderCard(data);
    };
    
    eventSource.onerror = function() {
        console.error('SSE connection failed. Retrying in 5 seconds...');
        eventSource.close();
        setTimeout(setupRealtimeUpdates, 5000);
    };
}

function updateFolderCard(data) {
    const folderCard = document.querySelector(`[data-folder-id="${data.folder_id}"]`);
    if (folderCard) {
        // Update video count
        const videoCountEl = folderCard.querySelector('.video-count');
        if (videoCountEl) {
            videoCountEl.textContent = `${data.video_count} videos`;
        }
        
        // Update last synced time
        const lastSyncedEl = folderCard.querySelector('.last-synced');
        if (lastSyncedEl) {
            lastSyncedEl.textContent = `Last synced: ${formatDate(data.last_synced)}`;
        }
        
        // Add a brief highlight effect
        folderCard.classList.add('updated');
        setTimeout(() => folderCard.classList.remove('updated'), 2000);
    }
}

// Folder management functions
function syncFolder(folderId) {
    if (!confirm('Are you sure you want to sync this folder?')) {
        return;
    }
    
    const button = event.target.closest('button');
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-sync fa-spin"></i> Syncing...';
    
    fetch(`/admin/drive-folder/${folderId}/sync/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            showNotification('Folder synced successfully', 'success');
            updateFolderStats(folderId, data);
        } else {
            showNotification(data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Error syncing folder', 'error');
    })
    .finally(() => {
        button.disabled = false;
        button.innerHTML = '<i class="fas fa-sync"></i> Sync Now';
    });
}

function deleteFolder(folderId) {
    if (!confirm('Are you sure you want to delete this folder? This will only remove the folder connection, not the actual Google Drive folder.')) {
        return;
    }
    
    fetch(`/admin/drive-folder/${folderId}/delete/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            const folderCard = document.querySelector(`[data-folder-id="${folderId}"]`);
            if (folderCard) {
                folderCard.remove();
            }
            showNotification('Folder deleted successfully', 'success');
        } else {
            showNotification(data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Error deleting folder', 'error');
    });
}

// Utility functions
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

function formatDate(dateString) {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return date.toLocaleString();
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('show');
    }, 100);
    
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    setupRealtimeUpdates();
    
    // Setup search functionality
    const searchInput = document.getElementById('folderSearch');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(function() {
            const searchTerm = this.value.toLowerCase();
            const folders = document.querySelectorAll('.folder-card');
            
            folders.forEach(folder => {
                const folderName = folder.querySelector('h3').textContent.toLowerCase();
                folder.style.display = folderName.includes(searchTerm) ? 'block' : 'none';
            });
        }, 300));
    }
});

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func.apply(this, args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
} 