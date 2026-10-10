-- Tabella dello score di rifornimento, scritta ogni giorno da esporta_score.py e letta da FuelMode.
-- Da eseguire una volta nell'editor SQL di Supabase (SQL Editor → New query → Run).

create table if not exists public.brent_score (
    data             date primary key,                          -- giorno di borsa del Brent
    esito            smallint not null check (esito in (-1, 0, 1)),
                                                               -- +1 rifornisci, 0 neutro, -1 aspetta
    score            double precision not null,                -- score continuo S
    brent_eur        double precision not null,                -- Brent in euro al barile
    media_30_eur     double precision not null,                -- media degli ultimi 30 giorni, euro al barile
    scarto           double precision not null,                -- ln(prezzo / media 30 giorni)
    oscillazione_5g  double precision not null,                -- oscillazione attesa in 5 giorni (frazione, 0.05 = 5%)
    stabilita        double precision not null,                -- fattore di stabilità, fra 0 e 1
    alpha            double precision not null,                -- sensibilità alla turbolenza usata
    theta            double precision not null,                -- soglia usata
    modello          text not null,                            -- modello dell'oscillazione attesa
    aggiornato_il    timestamptz not null default now()        -- quando è stata scritta la riga
);

comment on table public.brent_score is
    'Score di rifornimento dal prezzo del Brent: una riga per giorno di borsa (app Prezzo del petrolio).';

-- Chiunque abbia la chiave pubblica (anon) può leggere; scrive solo lo script, con la chiave service_role,
-- che non è soggetta alle regole RLS.
alter table public.brent_score enable row level security;

drop policy if exists "lettura dello score" on public.brent_score;
create policy "lettura dello score"
    on public.brent_score for select
    to anon, authenticated
    using (true);
