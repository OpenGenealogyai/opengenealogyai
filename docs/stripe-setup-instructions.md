# Stripe Payment Link Setup — OpenGenealogyAI

Step-by-step instructions for Garlon to activate the Buy Now buttons on pricing.html.

---

## Step 1 — Create a Free Stripe Account

1. Go to [stripe.com](https://stripe.com) and click **Start now**.
2. Enter your email, create a password, and verify your email address.
3. Complete the onboarding form: business name (OpenGenealogyAI), country, and business type.
4. You do not need a bank account connected to create Payment Links — but you will need one before you can receive payouts.

---

## Step 2 — Create Three Payment Links (one per tier)

Do this three times — once for each plan.

### For each plan:

1. In your Stripe Dashboard, go to **Products** in the left sidebar, then click **+ Add product**.
2. Fill in the product details:
   - **Name**: e.g. `Starter — 100 Research Actions`
   - **Description** (optional): e.g. `100 research actions per month. 50 roll over if unused.`
   - **Pricing model**: Recurring
   - **Price**: set the amount (see table below)
   - **Billing period**: Monthly
3. Click **Save product**.
4. After saving, click **Create payment link** on the product page (or go to **Payment Links** in the sidebar and click **+ New**).
5. Select the product you just created.
6. Click **Create link**.
7. Copy the URL — it will look like `https://buy.stripe.com/xxxxxxxxxxxxxxxx`.

### The three plans:

| Plan       | Price    | Actions/mo |
|------------|----------|------------|
| Starter    | $10/mo   | 100        |
| Researcher | $29/mo   | 350        |
| Pro        | $100/mo  | 1,250      |

---

## Step 3 — Replace the Placeholder URLs in pricing.html

Open `docs/pricing.html` and find this comment near line 75:

```
<!-- Replace PLACEHOLDER_* with real Stripe Payment Link URLs from dashboard.stripe.com -->
```

Replace the three placeholder URLs in the `href` attributes of the Buy Now buttons:

| Find this                                          | Replace with your real URL          |
|----------------------------------------------------|-------------------------------------|
| `https://buy.stripe.com/PLACEHOLDER_STARTER`       | Your Starter Payment Link URL       |
| `https://buy.stripe.com/PLACEHOLDER_RESEARCHER`    | Your Researcher Payment Link URL    |
| `https://buy.stripe.com/PLACEHOLDER_PRO`           | Your Pro Payment Link URL           |

Example of what the finished line should look like:
```html
<a href="https://buy.stripe.com/abc123xyz" class="btn-buy">Buy Now — $10/mo</a>
```

Save the file and push to GitHub Pages (or however you deploy the site).

---

## Step 4 — Test Before Going Live

1. In Stripe Dashboard, switch to **Test mode** (toggle in the top-left).
2. Create test Payment Links using a test product.
3. Click the link and pay using Stripe's test card: `4242 4242 4242 4242`, any future expiry, any CVC.
4. Confirm the payment appears in your Stripe Dashboard under **Payments**.
5. When you are satisfied, switch back to **Live mode** and use the live Payment Link URLs.

---

## Notes

- Payment Links do not require any code or webhook setup to collect payments.
- Customers will receive an automatic receipt from Stripe.
- You can view all subscribers under **Billing > Subscriptions** in the Dashboard.
- To add a customer portal (so subscribers can cancel or update their card), go to **Settings > Billing > Customer portal** and enable it.
