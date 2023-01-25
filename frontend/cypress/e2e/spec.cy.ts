/// <reference types="cypress" />

const Login = () => {
  cy.visit("http://localhost:8000/login");
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
    cy.url().should("eq", "http://localhost:8000/dashboard"); // => true
  });
});

describe("Testing Successful Plan Creation", () => {
  it("Test Plan creation flow", () => {
    Login();
    cy.visit("http://localhost:8000/create-plan");
    cy.wait(10000);
    cy.contains("Create Plan");
    cy.get("#create_plan_name").type("Random Plan");
    cy.get("#create_plan_description").type("Random Plan Description");
    cy.get("button#create-plan-button").click("");
    cy.wait(5000);
    cy.url().should("include", "/plans");
  });
});
