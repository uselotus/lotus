/* eslint-disable no-plusplus */
/// <reference types="cypress" />

function getId(length) {
  let result = "";
  const characters =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  const charactersLength = characters.length;
  for (let i = 0; i < length; i++) {
    result += characters.charAt(Math.floor(Math.random() * charactersLength));
  }
  return result;
}

function getEmail(length) {
  return `${getId(length)}@gmail.com`;
}

const Login = () => {
  cy.visit("http://localhost:3000/login");
  cy.contains("Username or Email");
  cy.get("[name='username']").type("demo4");
  cy.get("[name='password']").type("demo4");
  cy.get("form").contains("Login").click();
  cy.wait(5000);
  cy.on("uncaught:exception", (err) => {
    if (err.message.includes("_a6.join is not a function")) {
      return false;
    }
  });
};

describe("Testing Successful Login", () => {
  it("Navigates to Dashboard After Login", () => {
    cy.visit("http://localhost:3000"); // add this line to start on a fresh page
    Login();
    cy.contains("Dashboard");
    cy.url().should("eq", "http://localhost:3000/dashboard"); // => true
  });
});

describe("Testing Successful Plan Creation", () => {
  it("Test Plan creation flow", () => {
    Login();
    cy.visit("http://localhost:3000/create-plan");
    cy.wait(10000);
    cy.contains("Create a plan");
    cy.get("#planNameInput").type("Random Plan");
    cy.get("#planDescInput").type("Random Plan Description");
    cy.get("[type=radio]").check("monthly");

    //TODO : Add more tests for plan creation, creating recurring charges, creating components etc. and then double checking these on the plan details page
    cy.get("form").submit();
    cy.url().should("include", "/plans");
  });
});

describe("Testing Successful Metric Creation", () => {
  it("Test Metric creation flow", () => {
    Login();
    cy.visit("http://localhost:3000/metrics");
    cy.wait(10000);
    cy.get("#create-metric-button").click();
    cy.contains("Create Metric");
    cy.get("#define-new-metric").click();
    cy.get("#metric-name-input").type("New Metric");
    cy.get("#event-name-input").type("New event", { force: true });
    cy.get("#Create-metric-button").click();
  });
});

describe("Testing Create Customer and Attach Subscription", () => {
  it("Test Create customer flow", () => {
    Login();
    cy.visit("http://localhost:3000/customers");
    cy.wait(10000);
    cy.contains("Customers");
    cy.get("#create-cutsomer-model").click();
    cy.contains("Create a Customer");
    const randomId = getId(5);
    const randomEmail = getEmail(5);
    cy.get("#customer-name").type("Testing Customer");
    cy.get("#customer-email").type(randomEmail);
    cy.get("#customer-id").type(randomId);
    cy.get("#Create-customer-button").click();
    cy.wait(10000);
    cy.get(".ant-table-row").first().click();
  });
});

describe("Testing customer details tab", () => {
  it("renders the customer details properly", () => {
    Login();
    cy.visit("http://localhost:3000/customers");
    cy.wait(10000);
    cy.contains("Customers");
    cy.get(".ant-table-row").first().click();
    // go through tabs
    cy.wait(5000);
    cy.get("h1").contains("Customer Details");
    cy.get("h1").contains("Revenue Details");
    cy.get("h1").contains("Revenue vs Cost Per Day");
    // go to subscription tab
    cy.get(".ant-tabs-tab-btn").contains("Subscriptions").click();
    cy.wait(5000);
    cy.contains("Active Subscriptions");
    cy.get("h2").contains("Draft Invoice View");
    // go to Invoices tab
    cy.get(".ant-tabs-tab-btn").contains("Invoices").click();
    cy.wait(5000);
    cy.get("h2").contains("Invoices");
    cy.contains("Connections");
    cy.contains("Amount");
    // go to credits tab
    cy.get(".ant-tabs-tab-btn").contains("Invoices").click();
    cy.wait(5000);
    cy.contains("Credits");
  });
});

describe("Testing Event Tracking Details On Metrics Page", () => {
  it("Test event details on Metrics page", () => {
    Login();
    cy.visit("http://localhost:3000/settings/developer-settings");
    cy.contains("API Keys");
    cy.get(".ant-btn.ant-btn-primary").first().click();
    cy.contains("Create API Key");
    const apiKeyName = getId(16);
    cy.get(".ant-input").type(apiKeyName);
    cy.get(".ant-input[type=text]").should("have.value", apiKeyName);
    cy.get("[placeholder='Select date']").click();
    cy.get(".ant-picker-cell-today").siblings().last().click();
    cy.get(".ant-btn.ant-btn-primary.ant-btn-sm").click();
    cy.get(".ant-modal-footer .ant-btn.ant-btn-primary").click();
    cy.contains("Your new key is:");
    const eventName = "api_call";
    const date = new Date();
    const idempotencyId = getId(16);
    const customerId = getId(16);
    cy.get(".text-lg.font-main .ant-input").then(($input) => {
      const apiKey = $input.val();
      cy.get(".ant-modal-footer .ant-btn.ant-btn-primary").last().click();
      cy.request({
        url: "http://localhost:8000/api/track/",
        method: "POST",
        headers: {
          "X-API-KEY": apiKey,
          "Content-Type": "application/json",
        },
        body: {
          batch: [
            {
              event_name: eventName,
              properties: {
                region: "US",
              },
              time_created: date,
              idempotency_id: idempotencyId,
              customer_id: customerId,
            },
          ],
        },
      });
    });
    cy.visit("http://localhost:3000/metrics");
    cy.contains("Create Metric");
    cy.get(".ant-collapse-header").first().click();
    cy.wait(10000);
    // cy.contains("event_name").siblings().should("include.text", eventName);
    // cy.contains("customer_id").siblings().should("include.text", customerId);
    // cy.contains("ID").siblings().should("include.text", idempotencyId);
    // const dateString = date.toLocaleString("en-ZA").replace(",", "");
    // cy.contains("time_created").siblings().should("include.text", dateString);
    // cy.get(".travelcompany-input .input-label").should(
    //   "include.text",
    //   "region : US"
    // );
  });
});
