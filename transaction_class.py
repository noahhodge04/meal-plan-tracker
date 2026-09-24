class Transaction(object):
    def __init__(self, student, type, amount, location = "", note = ""):        
        self.student = student  # Student object
        self.type = type
        self.amount = amount
        self.location = location
        self.note = note
        # TODO: automatically track creation date

    def __str__(self):
        output = ""
        if(self.type == "swipe"):
            output += str(self.amount) + " " + str(self.type)
            if(self.amount > 1):
                output += "s"
        elif("Flex" in self.type):
            output += "$" + str(self.amount)
        if(self.location != ""):
            output += " at " + self.location

        # TODO: add an area for note
        return output

    # TODO: add getters and setters

# Testing
transactions = []
transactions.append(Transaction("james","swipe",1,location="Alpha"))
transactions.append(Transaction("james","swipe",2,location="Westy"))
transactions.append(Transaction("james","villageFlex",2.58))
transactions.append(Transaction("james","villageFlex",20.48,location="JazzBucks"))

for transaction in transactions:
    print(transaction)