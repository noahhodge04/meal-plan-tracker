async function reset_swipes(){
    try{
        const response = await fetch(
            "/api/swipes/reset",{
                method: "POST"
            }
        )
        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result,error || "Could not reset swipes");
        }

        window.location.href = "/";
    } catch(error) {
        console.error(error);
        alert(error.message || "Could not connect to the server. Please try again.");
    }
}