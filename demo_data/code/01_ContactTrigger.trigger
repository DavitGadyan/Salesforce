trigger ContactTrigger on Contact (after insert, after update) {
    for (Contact c : Trigger.new) {
        Account a = [SELECT Id, Name, Contact_Count__c FROM Account WHERE Id = :c.AccountId];
        a.Contact_Count__c = a.Contact_Count__c + 1;
        update a;
    }
}
