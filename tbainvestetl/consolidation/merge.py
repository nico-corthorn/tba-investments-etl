from tbainvestetl.domain_models.io import SQLParams
from tbainvestetl.utils import sql_manager


def merge_alpha_and_wrds_assets(sql_params: SQLParams):
    sql = sql_manager.ManagerSQL(sql_params)

    # Delete table
    sql.query("drop table if exists assets")

    # Read query for creating assets table
    query = """
create table assets as
select 
concat(case when w.ticker is null then coalesce(a.symbol, '0') else w.ticker end
	   , '-', coalesce(cast(permno as TEXT), '0')) as id
, coalesce(w.ticker, a.symbol) symbol
, w.permno
, a.name
, coalesce(a.exchange, w.primary_exch) exchange
, coalesce(a.asset_type, 'Stock') asset_type
, case 
	when coalesce(a.asset_type, 'Stock') = 'Stock' then coalesce(w.share_class, 'A')
	else w.share_class
	end share_class
, case 
	when ipo_date_proxy is not null and ipo_date is not null then 
		case when ipo_date_proxy < ipo_date then cast(ipo_date_proxy as date)
		else ipo_date end
	else cast(coalesce(ipo_date, ipo_date_proxy) as date) 
	end ipo_date
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
	select * 
	from (
		select *
		, row_number() over(partition by symbol order by coalesce(delisting_date, CURRENT_DATE) desc) rnk
		from assets_alpha
		where symbol not like '%-%'
		order by symbol, delisting_date
	) a
	where rnk = 1
) a
on 
w.delisting_date_proxy is NULL
and w.rnk=1
and a.symbol = w.ticker    
    """

    # Create assets table
    sql.query(query)


def merge_alpha_and_wrds_returns(sql_params: SQLParams):
    sql = sql_manager.ManagerSQL(sql_params)

    # Delete table
    sql.query("drop table if exists returns_monthly")

    # Read query for creating prices_monthly table
    query = """
create table returns_monthly as
select 
	id, symbol, period, date, source
	, close, adjusted_close, shares_outstanding
	, monthly_volume, monthly_return_std, monthly_return
	, row_number() over(partition by id, period order by priority) rnk
from (
	select a.id, a.symbol, period, date, source, priority
	, close, adjusted_close, shares_outstanding
	, monthly_volume, monthly_return_std, monthly_return
	from assets a
	left join (
		select 
		permno
		, to_char(date, 'YYYY-MM') period
		, cast(date as date) as date
		, 'WRDS' as source
		, 0 as priority
		, price as close
		, NULL::numeric adjusted_close
		, shrout shares_outstanding
		, volume_month as monthly_volume
		, std_month as monthly_return_std
		, ret_month as monthly_return
		from returns_wrds
	) w
	on w.permno = a.permno
	union
	select a.id, a.symbol, period, date, source, priority
	, close, adjusted_close, shares_outstanding
	, monthly_volume, monthly_return_std, monthly_return
	from assets a
	left join (
		select 
		symbol
		, to_char(date, 'YYYY-MM') period
		, date
		, 'ALPHA' as source
		, 1 as priority
		, close
		, adjusted_close
		, NULL::numeric shares_outstanding
		, monthly_volume
		, monthly_return_std
		, monthly_return
		, source_lud
		from prices_alpha_monthly
	) v
	on v.symbol = a.symbol and a.in_alpha = 1
) a
where date is not NULL
	"""

    # Create prices_montly table
    sql.query(query)
