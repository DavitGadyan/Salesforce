public with sharing class LeadRouter {
    public static void route(List<Lead> leads) {
        for (Lead l : leads) {
            List<User> reps = [SELECT Id FROM User WHERE Territory__c = :l.State AND IsActive = true];
            if (reps.size() > 0) {
                l.OwnerId = reps[0].Id;
            }
            Task t = new Task(Subject = 'Call new lead', WhoId = l.Id);
            insert t;
        }
        String json = JSON.serialize(leads);
        System.debug(json);
        Database.update(leads, false);
    }
}
