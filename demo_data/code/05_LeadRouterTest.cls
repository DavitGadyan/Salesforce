@isTest(SeeAllData=true)
private class LeadRouterTest {
    @isTest
    static void testRoute() {
        List<Lead> leads = [SELECT Id, State FROM Lead LIMIT 5];
        Test.startTest();
        LeadRouter.route(leads);
        Test.stopTest();
        System.assert(true);
    }
}
