# Cart management workflow

## Objective

Specify the complete guest Cart experience and its handoff to Checkout.

## Flow

Add product → mini-cart confirmation → review Cart → adjust integer quantity → review line totals and estimated total → continue shopping or proceed to Checkout.

Remove and Clear actions update local state immediately and expose Undo. Empty Cart returns to Shop. Error offers Retry. Offline mode keeps device-local management available. An unavailable product produces an explicit blocking message.

## Price and stock boundary

Frontend arithmetic is an interface specification using catalog mock prices. Future Cart/Checkout services must revalidate active Decimal prices, global sellability, quantity rules and fulfillment options. Customers never choose an operational branch. A manager or future `FulfillmentAssignmentService` assigns one after submission using inventory, proximity, workload and business rules. Cart changes do not create `InventoryMovement`, reserve stock, create `Order`, or initiate `Payment`.
