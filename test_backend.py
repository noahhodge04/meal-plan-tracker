from backend import get_balances, create_transaction, get_transactions, clear_transactions

print("Initial Balances:", get_balances())

#Test 1: Swipe deduction
#create_transaction("swipe", 1, location="Alpha", note="Lunch")

#Test 2: Village Flex rollover ($25 available, spending $28 -> $0 Village Flex, $12 Campus Flex)
#create_transaction("villageFlex", 28.00, location="JazzBucks", note="Coffee & Books")

#Test 3: Campus Flex deduction ($15 available, spending $10 -> $5 Campus Flex)
#create_transaction("campusFlex", 10.00, location="Campus Store", note="Mug")

clear_transactions()

print("Updated Balances:", get_balances())
print("Transaction History:", get_transactions())