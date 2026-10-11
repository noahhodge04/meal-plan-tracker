const form = document.querySelector("#submit-transaction")

async function sendData(){
    const formData = new FormData(form);

    try{
        const response = await fetch(
            "/api/transactions", {
                method: "POST",
                body: formData
            }
        );
        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.error || "Could not save the transaction.");
        }

        window.location.href = "/";
    } catch(error) {
        console.error(error);
        alert(error.message || "Could not connect to the server. Please try again.");
    }
}

form.addEventListener("submit", (event) => {
    event.preventDefault();
    sendData();
})