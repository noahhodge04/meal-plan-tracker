async function displayTransactionRecord() {
    try {
        const request = "/api/transactions";
        fetch(request)
            .then(response => response.json())
            .then(data => {
                console.log(data.data);
                list = document.getElementById("transaction-list");
                for(transaction of data.data){
                    li = document.createElement("li");
                    if(transaction.type == "swipe"){
                        li.textContent += `${transaction.amount} swipe`;
                        if(transaction.amount > 1){
                            li.textContent += 's';
                        }
                    } else{
                        li.textContent += `$${transaction.amount}`;
                    }
                    if(transaction.location){
                        li.textContent += ` at ${transaction.location}`
                    } 
                    if(transaction.note){
                        li.textContent += ` (${transaction.note})`
                        }
                    list.appendChild(li);
                }
            });
    } catch(error){
        console.log("could not fetch transaction record");
    }
}

displayTransactionRecord();