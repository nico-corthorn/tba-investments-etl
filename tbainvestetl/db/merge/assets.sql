
/* 
	We join the ticker-permno in WRDS with the lowest class share (normally A) and the highest delisting date (or none if available)
	with the first ticker in AlphaVantage that has delisting date higher than last date in WRDS
*/

create table assets as
select
id
, symbol
, permno
, name
, exchange
, asset_type
, share_class
, ipo_date_wrds
, ipo_date_alpha
, ipo_date
, delisting_date_wrds
, delisting_date_alpha
, delisting_date
, in_alpha
, alpha_lud
, lud
from (
	select *
	, concat(symbol_permno, '-', row_number() over(partition by symbol_permno order by delisting_date asc NULLS last)) id
	from (
		select 
		concat(case when w.ticker is null then coalesce(a.symbol, '0') else w.ticker end
			   , '-', coalesce(cast(permno as TEXT), '0')) as symbol_permno
		, coalesce(w.ticker, a.symbol) symbol
		, w.permno
		, a.name
		, coalesce(a.exchange, w.primary_exch) exchange
		, coalesce(a.asset_type, 'Stock') asset_type
		, case 
			when coalesce(a.asset_type, 'Stock') = 'Stock' then coalesce(w.share_class, 'A')
			else w.share_class
			end share_class
		, ipo_date_proxy ipo_date_wrds
		, ipo_date ipo_date_alpha
		, case
			when ipo_date_proxy is not null and ipo_date is not null then 
				case when ipo_date_proxy < ipo_date then cast(ipo_date_proxy as date)
				else ipo_date end
			else cast(coalesce(ipo_date, ipo_date_proxy) as date) 
			end ipo_date
		, delisting_date_proxy delisting_date_wrds
		, delisting_date delisting_date_alpha
		, cast(coalesce(delisting_date, delisting_date_proxy) as date) delisting_date
		, case when a.symbol is not null then 1 else 0 end in_alpha
		, case 
			when a.status is null and delisting_date_proxy is not null then 'Delisted' 
			else a.status
		  end status
		, lud alpha_lud
		, Now() lud
		from assets_wrds w
		full outer join (
			select
			replace(symbol, '-A', '') symbol
			, name
			, exchange
			, asset_type
			, ipo_date
			, delisting_date
			, status
			, lud
			, row_number() over(partition by symbol order by coalesce(delisting_date, CURRENT_DATE)) rnk
			from assets_alpha
			where ((symbol not like '%-%') or ((symbol like '%-A') and (length(symbol) - length(replace(symbol, '-', '')) = 1)))
				  and (name not like '%- Unit%') -- no Units (stock + warrant)
				  and (name not like '%Warrant%') -- no Warrants
				  and ((name not like '%- Class %') or (name like '%- Class A%')) -- no Stocks with class other than A
				  and (coalesce(delisting_date, CURRENT_DATE) >= (select max(date) from returns_wrds)) -- delisting_date in AlphaVantage is either missing or higher than highest in WRDS
			--order by symbol, delisting_date
		) a
		on 
		w.delisting_date_proxy is NULL -- Join only WRDS assets that were not delisted at the time
		and w.rnk = 1  -- Ticker-permno in WRDS with the lowest class share (normally A) and the highest delisting date or none if available (newest).
		and a.rnk = 1  -- Choose the first one (oldest) in AlphaVantage that satisfies delisting condition
		and a.symbol = w.ticker
		where
			not (w.permno is null and a.asset_type = 'Stock' and length(a.symbol) > 4) -- Avoid AlphaVantage stocks with more than 4 characters since those are special issues
	) a
) a
order by id, ipo_date
;

--alter table assets add primary key (id);