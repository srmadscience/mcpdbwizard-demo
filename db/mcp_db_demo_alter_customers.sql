-- Adds PHONE_NUMBER and EMAIL_ADDRESS to an existing CUSTOMERS table.
--
-- Only needed for a schema created before those columns existed.
-- A fresh install should run mcp_db_demo_ddl.sql instead, which already
-- creates CUSTOMERS with all three columns.
--
-- The UPSERT_CUSTOMER procedure is NOT repeated here. It is CREATE OR
-- REPLACE, so run that part of mcp_db_demo_ddl.sql as-is after this script.

ALTER TABLE customers ADD
   (   "PHONE_NUMBER"   VARCHAR2(20 BYTE),
       "EMAIL_ADDRESS"  VARCHAR2(80 BYTE));

-- Give the existing sample customers the same contact details a fresh
-- install gets from mcp_db_demo_dml.sql

UPDATE customers SET phone_number = '+36 1 555 0101', email_address = 'm.gustave@grandbudapest.zz'
WHERE  customer_name = 'M GUSTAVE';

UPDATE customers SET phone_number = '+36 1 555 0102', email_address = 'zero.moustafa@grandbudapest.zz'
WHERE  customer_name = 'ZERO MOUSTAFA';

UPDATE customers SET phone_number = '+36 1 555 0103', email_address = 'agatha@mendls.zz'
WHERE  customer_name = 'AGATHA';

UPDATE customers SET phone_number = '+1 401 555 0110', email_address = 'suzy.bishop@newpenzance.zz'
WHERE  customer_name = 'SUZY BISHOP';

UPDATE customers SET phone_number = '+1 401 555 0111', email_address = 'sam.shakusky@khakiscouts.zz'
WHERE  customer_name = 'SAM SHAKUSKY';

UPDATE customers SET phone_number = '+33 4 555 0120', email_address = 'steve.zissou@belafonte.zz'
WHERE  customer_name = 'STEVE ZISSOU';

UPDATE customers SET phone_number = '+49 30 555 0121', email_address = 'klaus.daimler@belafonte.zz'
WHERE  customer_name = 'KLAUS DAIMLER';

UPDATE customers SET phone_number = '+91 141 555 0130', email_address = 'francis.whitman@darjeeling.zz'
WHERE  customer_name = 'FRANCIS WHITMAN';

UPDATE customers SET phone_number = '+1 505 555 0140', email_address = 'augie.steenbeck@asteroidcity.zz'
WHERE  customer_name = 'AUGIE STEENBECK';

UPDATE customers SET phone_number = '+33 1 555 0150', email_address = 'roebuck.wright@frenchdispatch.zz'
WHERE  customer_name = 'ROEBUCK WRIGHT';

UPDATE customers SET phone_number = '+1 212 555 0160', email_address = 'margot.tenenbaum@tenenbaum.zz'
WHERE  customer_name = 'MARGOT TENENBAUM';

UPDATE customers SET phone_number = '+44 20 555 0170', email_address = 'mr.fox@foxholdings.zz'
WHERE  customer_name = 'MR FOX';

UPDATE customers SET phone_number = '+1 713 555 0180', email_address = 'herman.blume@blumeintl.zz'
WHERE  customer_name = 'HERMAN BLUME';

COMMIT;

-- Only enforceable once every existing row has been given values above

ALTER TABLE customers MODIFY
   (   "PHONE_NUMBER"   NOT NULL,
       "EMAIL_ADDRESS"  NOT NULL);

ALTER TABLE customers ADD CONSTRAINT "CUSTOMERS_EMAIL_HAS_AT"
   CHECK (EMAIL_ADDRESS LIKE '%@%') ENABLE;

-- Built after the backfill so each index is populated in one pass

CREATE UNIQUE INDEX "CUSTOMERS_EMAIL_ADDRESS" ON "CUSTOMERS" ("EMAIL_ADDRESS");

CREATE UNIQUE INDEX "CUSTOMERS_PHONE_NUMBER" ON "CUSTOMERS" ("PHONE_NUMBER");
