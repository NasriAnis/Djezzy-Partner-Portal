# Djezzy Partner Portal — internals Guide

# Admin
The admin has the power to create commercials accounts.

---
# Commercials
### Accounts
Commercials account can only be created by an Admin via the `/admin` panel, to login head to `/commercial/login`.
### Details
A commercial account can create/modify/delete offers and manages user stores demands.

A commercial get assigned to it stores to manage depending on its load the algorithm for that can be found at `/clients/services` line 6.

---
# Users
A user can create stores that are put in pending waiting for one commercial approval.

---
# Offers
### How an offer is created
Before creating an offer it has to be categories like `postpayee`, `prepayee` etc..., then when creating an offer a category has to be selected. This new offer row in the DB get linked to the category selected row. Below each offer plans can be created at `/commercial/offers/<offer>/edit/`.