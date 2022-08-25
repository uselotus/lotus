import React, { FC, useEffect, useState } from "react";
import CustomerTable from "../components/CustomerTable";
import { CustomerType } from "../types/customer-type";
import { Customer } from "../api/api";
import * as Toast from "@radix-ui/react-toast";
import { useNavigate } from "react-router-dom";
import { Authentication } from "../api/api";
import "./Login.css";

interface LoginForm extends HTMLFormControlsCollection {
  username: string;
  password: string;
}

interface FormElements extends HTMLFormElement {
  readonly elements: LoginForm;
}

const Login: FC = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const navigate = useNavigate();

  const handlePasswordChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setPassword(event.target.value);
  };

  const handleUserNameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setUsername(event.target.value);
  };

  const redirectDashboard = () => {
    navigate("/dashboard");
  };

  const handleLogin = (event: React.FormEvent<FormElements>) => {
    event.preventDefault();
    Authentication.login(username, password).then((data) => {
      setIsAuthenticated(true);
    });
  };

  if (!isAuthenticated) {
    return (
      <>
        <div className="container mt-3">
          <img src="../assets/images/logo_large.jpg" alt="logo" />
          <h2>Login</h2>
          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label htmlFor="username">Username</label>
              <input
                type="text"
                className="form-control"
                id="username"
                name="username"
                value={username}
                onChange={handleUserNameChange}
              />
            </div>
            <div className="form-group">
              <label htmlFor="username">Password</label>
              <input
                type="password"
                className="form-control"
                id="password"
                name="password"
                value={password}
                onChange={handlePasswordChange}
              />
              <div>
                {error && <small className="text-danger">{error}</small>}
              </div>
            </div>
            <button type="submit" className="btn btn-primary">
              Login
            </button>
          </form>
        </div>
      </>
    );
  }
  return (
    <div className="container mt-3">
      <h1>Login</h1>
      <p>Hi {username}. You are logged in!</p>
      <button className="btn btn-primary mr-2" onClick={redirectDashboard}>
        Dashboard
      </button>
      <button className="btn btn-danger">Log out</button>
    </div>
  );
};

export default Login;
