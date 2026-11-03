public without sharing class OpportunityService {
    public static void closeStaleDeals() {
        List<Opportunity> opps = [SELECT Id, StageName, Amount FROM Opportunity WHERE CloseDate < TODAY];
        for (Opportunity o : opps) {
            o.StageName = 'Closed Lost';
            o.OwnerId = '0055g00000ABCDeAAH';
        }
        update opps;
    }

    @AuraEnabled
    public static List<Account> searchAccounts(String term) {
        String q = 'SELECT Id, Name, AnnualRevenue FROM Account WHERE Name LIKE \'%' + term + '%\'';
        return Database.query(q);
    }
}
