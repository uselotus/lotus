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
  cy.on("uncaught:exception", (err, runnable) => {
    if (err.message.includes("_a6.join is not a function")) {
      return false;
    }
  });
};

describe("Testing Successful Login", () => {
  it("Navigates to Dashboard After Login", () => {
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
    cy.contains("Create Plan");
    cy.get("#planNameInput").type("Random Plan");
    cy.get("#planDescInput").type("Random Plan Description");
    cy.get("[type=radio]").check("monthly");
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
    cy.get("#Metric-Name-input").type("New Metric");
    cy.get("#event-name-input").type("New event");
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

describe("Testing Event Tracking Details On Metrics Page", () => {
  it("Test event details on Metrics page", () => {
    Login();
    // Navigate to the Settings -> Developer Settings page
    cy.visit("http://localhost:3000/settings/developer-settings");
    cy.contains("API Keys");
    // Click the "Add API Key" button
    cy.get(".ant-btn.ant-btn-primary").first().click();
    cy.contains("Create API Key");
    const apiKeyName = getId(16);
    // Enter text for the "API Key Name" field
    cy.get(".ant-input").type(apiKeyName);
    cy.get(".ant-input[type=text]").should("have.value", apiKeyName);
    // Select a date for the "Expiry Date + Time" field
    cy.get("[placeholder='Select date']").click();
    cy.get(".ant-picker-cell-today").siblings().last().click();
    // Click OK button in date picker
    cy.get(".ant-btn.ant-btn-primary.ant-btn-sm").click();
    // Click the "Confirm" button
    cy.get(".ant-modal-footer .ant-btn.ant-btn-primary").click();
    cy.contains("Your new key is:");
    // Copy the API key that is displayed
    cy.get(".text-lg.font-main .ant-input").then(($input) => {
      const apiKey = $input.val();
    // Click Okay button in modal
    cy.get(".ant-modal-footer .ant-btn.ant-btn-primary").last().click();
    // Send request to /api/track/ endpoint
      cy.request({
        url: "http://localhost:8000/api/track/",
        method: "POST",
        headers: {
          "X-API-KEY": apiKey,
          "Content-Type": "application/json"
        },
        body: {
          "batch": [{
            "event_name": "api_call",
            "properties": {
              "region": "US"
            },
            "time_created": new Date(),
            "idempotency_id": "test_idempotency_id_123",
            "customer_id": "test_customer_id_123"
          }]
        }
      }).then(({ body }) => {
        cy.log(`body: ${body}`);
      });
    });
    // Navigate to the Metrics page
    cy.visit("http://localhost:3000/metrics");
    cy.contains("Create Metric");
    // Verify that the event details section displays a new event with the following fields: customer_id, event_name, ID, time_created
    // Verify fields of newly created event match the data that was supplied in the request
  });
});
