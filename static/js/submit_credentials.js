const form = document.querySelector("#submit-credentials")
const currentScript = document.currentScript;
const interface = currentScript.dataset.interface;
const redirect = currentScript.dataset.redirect;

async function submitCredentials(){
    const formData = new FormData(form);
    console.log(formData);
    try{
        const response = await fetch(
            `/api/${interface}`, {
                method: "POST",
                body: formData
            }
        );
        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.error || "Could not log in.");
        }

        window.location.href = redirect;
    } catch(error) {
        console.error(error);
        alert(error.message || "Could not connect to the server. Please try again.");
    }
}

form.addEventListener("submit", (event) => {
    event.preventDefault();
    submitCredentials();
})