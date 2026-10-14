const notificationSettingsForm = document.getElementById("notification-settings-form");
const notificationSettingsStatus = document.getElementById("notification-settings-status");
const thresholdFields = [
    "swipe_alert_threshold",
    "village_flex_alert_threshold",
    "campus_flex_alert_threshold",
];

async function loadNotificationSettings() {
    try {
        const response = await fetch("/api/notification-settings");
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.error || "Could not load alert settings.");
        }

        for (const field of thresholdFields) {
            notificationSettingsForm.elements[field].value = result.data[field] ?? "";
        }
    } catch (error) {
        notificationSettingsStatus.textContent = error.message || "Could not load alert settings.";
    }
}

async function saveNotificationSettings(event) {
    event.preventDefault();
    const settings = Object.fromEntries(new FormData(notificationSettingsForm));

    try {
        const response = await fetch("/api/notification-settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(settings),
        });
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.error || "Could not save alert settings.");
        }
        notificationSettingsStatus.textContent = "Alert settings saved.";
        for (const field of thresholdFields) {
            notificationSettingsForm.elements[field].value = result.data[field] ?? "";
        }
    } catch (error) {
        notificationSettingsStatus.textContent = error.message || "Could not save alert settings.";
    }
}

notificationSettingsForm.addEventListener("submit", saveNotificationSettings);
loadNotificationSettings();
