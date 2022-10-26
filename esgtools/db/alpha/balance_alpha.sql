-- DROP TABLE balance_alpha

CREATE TABLE balance_alpha
(
	symbol varchar(20) NOT NULL,
	report_type varchar(1) NOT NULL, 
	report_date date NOT NULL,
	currency varchar(3) NOT NULL,
	account_name text NOT NULL,
	account_value bigint, 
	PRIMARY KEY (symbol, report_type, report_date, currency, account_name)
)

