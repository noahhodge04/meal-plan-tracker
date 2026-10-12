async function displayBalance() {
    try {
        const request = "/api/balances";
        fetch(request)
            .then(response => response.json())
            .then(data => {
                document.getElementById("balance-field").innerHTML = `
                Swipes: ${data.data.swipes} </br>
                Flex: $${data.data.village_flex} </br>
                Campus Store Flex: $${data.data.campus_flex}
                `
            });
    } catch(error){
        console.log("could not fetch balance");
    }
}

displayBalance();