/// <reference types="cypress" />

const Login = () => {
    cy.visit('http://localhost:8000/login')
    cy.contains('Username or Email')
    cy.get("#username").type("lotus");
    cy.get("#password").type("hardik");
    cy.get('form').contains('Login').click()
    cy.wait(10000)
}

describe('Testing Successful Login', () => {
    it('Navigates to Dashboard After Login', () => {
        Login()
        cy.contains("Dashboard")
        cy.url().should('eq', "http://localhost:8000/dashboard") // => true
    })
})

describe('Testing Successful Plan Creation', () => {
    it('Test Plan creation flow', () => {
        Login();
        cy.visit('http://localhost:8000/create-plan');
        cy.wait(10000)
        cy.contains('Create Plan');
        cy.get("#planNameInput").type("Random Plan");
        cy.get("#planDescInput").type("Random Plan Description");
        cy.get('[type="radio"]').check("monthly");
        cy.get('form').submit()
    })
})
