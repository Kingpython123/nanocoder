# Discount rules

An invoice can carry several discounts (coupons). They are applied to the invoice
gross amount (subtotal + tax) in this order:

1. **Percentage discounts first.** Each one is applied to the amount left after
   the previous percentage discount, so two 10 % coupons give 19 % off in total,
   not 20 %. The order in which percentage coupons were added does not matter.
2. **Fixed-amount discounts next**, subtracted from the result of step 1.
3. The result never goes below zero.
4. Rounding to cents happens once, at the very end.

A percentage discount must be between 0 and 100. A fixed discount must not be
negative.
