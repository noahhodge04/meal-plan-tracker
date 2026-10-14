const notificationsList = document.getElementById("notification-list");
const notificationsStatus = document.getElementById("notifications-status");

async function markNotificationRead(notificationId, item) {
    try {
        const response = await fetch(`/api/notifications/${notificationId}/read`, {
            method: "POST",
        });
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.error || "Could not mark notification as read.");
        }
        item.remove();
        if (notificationsList.children.length === 0) {
            notificationsStatus.textContent = "No unread notifications.";
        }
    } catch (error) {
        notificationsStatus.textContent = error.message || "Could not update notification.";
    }
}

async function loadNotifications() {
    try {
        const response = await fetch("/api/notifications");
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.error || "Could not load notifications.");
        }

        const unreadNotifications = result.data.filter(notification => !notification.is_read);
        notificationsList.replaceChildren();
        if (unreadNotifications.length === 0) {
            notificationsStatus.textContent = "No unread notifications.";
            return;
        }
        notificationsStatus.textContent = "";

        for (const notification of unreadNotifications) {
            const item = document.createElement("li");
            item.className = "list-group-item list-group-item-warning";
            const title = document.createElement("strong");
            title.textContent = notification.title;
            const message = document.createElement("p");
            message.textContent = notification.message;
            item.append(title, message);

            const button = document.createElement("button");
            button.type = "button";
            button.className = "btn btn-sm btn-outline-secondary";
            button.textContent = "Mark as read";
            button.addEventListener("click", () => {
                markNotificationRead(notification.id, item);
            });
            item.append(button);
            notificationsList.append(item);
        }
    } catch (error) {
        notificationsStatus.textContent = error.message || "Could not load notifications.";
    }
}

loadNotifications();
