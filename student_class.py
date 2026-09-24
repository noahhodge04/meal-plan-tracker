from transaction_class import Transaction

class Student(object):
    def __init__(self, id, name):
        # class variable definitions
        self.id = id
        self.name = name
        self.transactions = []

    # class methods
    def startBalance(self,swipes,villageFlex,campusFlex):
        self.swipes = swipes
        self.villageFlex = villageFlex
        self.campusFlex = campusFlex

    def resetSwipes(self):
        pass

    # TODO: Test this method
    def createTransaction(self, type, amount, location="", note=""):
        # Updates the balance, then creates a Transaction object to record the change
        if type not in ("swipe", "villageFlex","campusFlex"):  # Ensures that the type is accepted and will be properly processed
            raise Exception("type must be 'swipe', 'villageFlex', or 'campusFlex'")
        if(type == "swipe"):
            self.swipes -= amount
        elif(type == "villageFlex"):
            self.villageFlex -= amount
            if(self.villageFlex < 0):                                                                     # If village flex runs out,
                self.campusFlex += self.villageFlex                                                       # takes the remainder out of campus flex,
                self.transactions.append(Transaction(self,"CampusFlex",-self.villageFlex,location,note))  # logs the campus flex transaction,
                amount += self.villageFlex                                                                # changes the amount of the main transaction to match what was actually taken out,
                self.villageFlex = 0                                                                      # and resets the village flex to account for taking out of campus flex
        elif(type == "campusFlex"):
            self.campusFlex -= amount
        self.transactions.append(
            Transaction(self,type,amount,location,note)
        )

    # TODO: Setters
    # getters
    def getID(self): return self.id
    def getName(self): return self.name
    def getSwipes(self): return self.swipes
    def getVillageFlex(self): return self.villageFlex
    def getCampusFlex(self): return self.campusFlex
    def getTransactionRecord(self): return self.transactions