const form = document.querySelector("#starting-balance")

async function setStartingBalance(){
    const formData = new FormData(form);
    try{
        const response = await fetch(
            "/api/setup/balances", {
                method: "POST",
                body: formData
            }
        );
        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.error || "Could not set starting balance");
        }

        window.location.href = "/";
    } catch(error) {
        console.error(error);
        alert(error.message || "Could not connect to the server. Please try again.");
    }
}

form.addEventListener("submit", (event) => {
    event.preventDefault();
    setStartingBalance();
})