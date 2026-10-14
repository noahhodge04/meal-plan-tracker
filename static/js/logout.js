async function logout(){
    try{
        const response = await fetch(
            "/api/logout",{
                method: "POST"
            }
        )
        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result,error || "Could not log out");
        }

        window.location.href = "/login";
    } catch(error) {
        console.error(error);
        alert(error.message || "Could not connect to the server. Please try again.");
    }
}