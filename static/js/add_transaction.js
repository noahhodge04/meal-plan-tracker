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
        window.location.href = "/";
    } catch(error) {
        console.error(error);
    }
}

form.addEventListener("submit", (event) => {
    event.preventDefault();
    sendData();
})