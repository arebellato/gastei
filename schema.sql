-- Meu Mercado: rode tudo isto de uma vez no SQL Editor do Supabase

create table if not exists categorias (
  nome text primary key
);

insert into categorias (nome) values
  ('Hortifruti'), ('Carnes e peixes'), ('Frios e laticínios'), ('Padaria'),
  ('Mercearia'), ('Bebidas'), ('Bebidas alcoólicas'), ('Congelados'),
  ('Doces e snacks'), ('Limpeza'), ('Higiene e beleza'), ('Pet'),
  ('Utilidades'), ('Outros')
on conflict do nothing;

create table if not exists produtos (
  id bigint generated always as identity primary key,
  nome_padrao text not null unique,
  categoria text not null default 'Outros',
  criado_em timestamptz default now()
);

-- "de/para": cada descrição do cupom (normalizada) aponta para um produto padrão
create table if not exists apelidos (
  descricao_norm text primary key,
  produto_id bigint not null references produtos(id) on delete cascade
);

create table if not exists compras (
  id bigint generated always as identity primary key,
  chave text unique,                 -- chave de acesso da NFC-e (vazia em lançamento manual)
  mercado text not null,
  cnpj text,
  data date not null,
  hora time,
  total numeric(12,2) not null,
  origem text not null default 'nfce', -- 'nfce' ou 'manual'
  registrado_por text,
  url text,
  observacao text,
  criado_em timestamptz default now()
);

create table if not exists itens (
  id bigint generated always as identity primary key,
  compra_id bigint not null references compras(id) on delete cascade,
  produto_id bigint references produtos(id) on delete set null,
  descricao_original text not null,
  codigo text,
  quantidade numeric(12,4) default 1,
  unidade text,
  valor_unitario numeric(12,4),
  valor_total numeric(12,2) not null
);

create index if not exists idx_itens_compra on itens(compra_id);
create index if not exists idx_itens_produto on itens(produto_id);
create index if not exists idx_compras_data on compras(data);

-- Segurança: bloqueia acesso público. O app usa a chave secreta, que ignora o RLS.
alter table categorias enable row level security;
alter table produtos   enable row level security;
alter table apelidos   enable row level security;
alter table compras    enable row level security;
alter table itens      enable row level security;
