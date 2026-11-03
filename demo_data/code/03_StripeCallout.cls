public class StripeCallout {
    @future
    public static void chargeCustomers(List<Id> invoiceIds) {
        for (Id invId : invoiceIds) {
            Invoice__c inv = [SELECT Id, Amount__c, Stripe_Customer__c FROM Invoice__c WHERE Id = :invId];
            HttpRequest req = new HttpRequest();
            req.setEndpoint('https://api.stripe.com/v1/charges');
            req.setHeader('Authorization', 'Bearer sk_live_51HxYzABCDEF');
            req.setMethod('POST');
            req.setBody('amount=' + inv.Amount__c + '&customer=' + inv.Stripe_Customer__c);
            HttpResponse res = new Http().send(req);
            inv.Status__c = res.getStatusCode() == 200 ? 'Paid' : 'Failed';
            update inv;
        }
    }
}
