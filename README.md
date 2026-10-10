# Meu Mercado

App para ler o QR Code do cupom fiscal (NFC-e), guardar os itens, categorizar e analisar os gastos de mercado. Também aceita lançamento manual (feira, sacolão, compra sem nota).

## O que tem no app

| Tela | O que faz |
|---|---|
| 📷 Nota | Lê o link ou a foto do QR Code, busca a nota na SEFAZ, sugere produto padrão e categoria, e salva. Bloqueia nota repetida. |
| ✍️ Manual | Lança compra sem nota, com itens ou só com o valor total e a categoria. |
| 📊 Análises | Gasto por mês, categoria, mercado e produto, histórico de preço por produto e por mercado, e a "lista do mês" (o que você compra sempre). |
| 🧾 Histórico | Compras por mês, itens de cada uma, exclusão e exportação para CSV. |
| 🏷️ Produtos | Renomear produto, trocar categoria, juntar produtos iguais, corrigir descrição ligada ao produto errado e criar categorias. |

### Como funciona a junção de itens iguais

Cada descrição do cupom ("LEITE UHT ITALAC INT 1L") fica ligada a um **produto padrão** ("Leite integral 1L"). As análises usam sempre o produto padrão.

1. Descrição que já apareceu antes: o app já sabe qual é o produto (✅).
2. Descrição muito parecida com uma conhecida: sugere o mesmo produto (🔁).
3. Descrição nova: sugere nome e categoria por regras de palavra-chave, ou pelo Claude se você configurar a chave da API (🆕).

Você revisa antes de salvar. Cada correção vira regra para as próximas notas, então em poucas semanas quase tudo fica automático.

## Passo a passo

### 1. GitHub (onde fica o código)
1. Crie uma conta em github.com, se ainda não tiver.
2. Crie um repositório **privado** chamado `meu-mercado`.
3. Suba os arquivos desta pasta (botão "Add file > Upload files"). Inclua a pasta `.streamlit` só com o `secrets.toml.example`. **Nunca suba o `secrets.toml` real.**

### 2. Supabase (o banco de dados)
1. Crie uma conta em supabase.com e um novo projeto. Escolha a região **South America (São Paulo)**.
2. No menu lateral, abra **SQL Editor**, cole o conteúdo de `schema.sql` e clique em **Run**.
3. Em **Project Settings > API Keys** (ou "API"), copie:
   - a **Project URL** (vai em `SUPABASE_URL`)
   - a chave **secret** (ou `service_role`) (vai em `SUPABASE_KEY`)

A chave secret dá acesso total ao banco. Ela fica só nos Secrets do Streamlit, nunca no código.

### 3. Chave do Claude (opcional, recomendado)
1. Em console.anthropic.com, crie uma chave de API e coloque um crédito pequeno.
2. Ela vai em `ANTHROPIC_API_KEY`. O app usa o modelo Haiku, só para itens novos, então o custo por nota é de centavos.
3. Sem a chave, o app funciona normalmente com as regras de palavra-chave.

### 4. Testar no seu computador (recomendado antes de publicar)
```bash
cd meu-mercado
python -m venv .venv
.venv\Scripts\activate          # Windows  (no Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .streamlit\secrets.toml.example .streamlit\secrets.toml   # e preencha
streamlit run app.py
```
Leia um cupom de verdade para confirmar que a consulta na SEFAZ funciona.

Dica: o terminal mostra um "Network URL". Com o celular no mesmo Wi-Fi, abrindo esse endereço, você já testa pelo celular.

### 5. Publicar (Streamlit Community Cloud, grátis)
1. Entre em share.streamlit.io com a conta do GitHub.
2. **Create app > Deploy a public app from GitHub**, escolha o repositório, branch `main`, arquivo `app.py`.
3. Em **Advanced settings > Secrets**, cole o conteúdo do seu `secrets.toml` preenchido.
4. Clique em **Deploy**. Em alguns minutos você recebe o link.

### 6. Usar no celular
1. Abra o link no navegador do celular e use "Adicionar à tela inicial". Fica com cara de app.
2. Mande o link e a senha para a Gi. Na tela de entrada cada um escolhe o próprio nome, e as análises podem filtrar por quem registrou.

## Dicas de uso
- **Ler o QR Code**: o mais confiável é usar a câmera nativa do celular, segurar no link que aparece, copiar e colar no app. A foto dentro do app também funciona, mas depende de luz e foco.
- Nota recém-emitida às vezes ainda não aparece na SEFAZ. Se der erro, tente de novo mais tarde.
- Para comprar o mesmo produto em marcas diferentes e comparar preço, mantenha o nome padrão sem marca ("Café 500g"). Se preferir separar por marca, é só incluir a marca no nome.
- Itens vendidos por kg têm o preço unitário por kg, o que permite comparar entre mercados.

## Se a consulta à SEFAZ falhar depois de publicar
Os servidores do Streamlit Cloud ficam fora do Brasil, e alguns portais da SEFAZ às vezes recusam acesso de fora. Se no seu computador funciona e publicado não:
1. **Rodar em casa**: deixe `streamlit run app.py` rodando num PC e acesse pelo celular no Wi-Fi (o banco continua na nuvem, então nada se perde).
2. **Servidor no Brasil**: publicar numa máquina gratuita da Oracle Cloud (região São Paulo) ou numa VPS brasileira barata.

Enquanto isso, o lançamento manual sempre funciona.

## Ajustes fáceis
- Regras de categoria: dicionário `REGRAS` em `categorize.py`.
- Sensibilidade da junção automática: `LIMIAR_SIMILARIDADE` em `categorize.py` (90 é conservador).
- Instruções de padronização para o Claude: função `sugerir_com_claude` em `categorize.py`.
