-- ---------------------------------------------------------------------------
-- شغل هاد الكود مرة وحدة فـ Supabase > SQL Editor > New query > Run
-- ---------------------------------------------------------------------------

-- الجدول اللي غادي يخزن عدد الاستعمال ديال كل كود
create table if not exists usage_counters (
    key         text primary key,
    count       integer not null default 0,
    first_used  timestamptz,
    last_used   timestamptz
);

-- دالة atomic: كتزيد 1 فالعداد (أو كتخلق السطر إلا ماكانش موجود)
-- استعمال دالة SQL بدل "read then write" من Python كيحمينا من مشاكل
-- التزامن إلا كان أكثر من زبون كيسحب فنفس اللحظة بالضبط.
create or replace function increment_usage(key_input text)
returns integer
language plpgsql
as $$
declare
    new_count integer;
begin
    insert into usage_counters (key, count, first_used, last_used)
    values (key_input, 1, now(), now())
    on conflict (key)
    do update set
        count = usage_counters.count + 1,
        last_used = now()
    returning count into new_count;

    return new_count;
end;
$$;
