import React, { FC, useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Card, Input, Button, Form } from "antd";
import "./CreateOrganization.css";
import { useQueryClient } from "react-query";

interface LoginForm extends HTMLFormControlsCollection {
  username: string;
  password: string;
}

interface Organizaton {
  company_name: string;
  industry: string;
}

interface FormElements extends HTMLFormElement {
  readonly elements: LoginForm;
}

const CreateOrganization = (props: { onSave: (org: Organizaton) => void }) => {
  const [companyName, setCompanyName] = useState("");
  const [error, setError] = useState("");
  const queryClient = useQueryClient();

  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const navigate = useNavigate();

  const handleNameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setCompanyName(event.target.value);
  };

  const redirectDashboard = () => {
    navigate("/dashboard");
  };

  const handleCreate = (event: React.FormEvent<FormElements>) => {
    Authentication.login(username, password).then((data) => {
      setIsAuthenticated(true);
      queryClient.invalidateQueries("session");
    });
  };

  if (!isAuthenticated) {
    return (
      <>
        <div className="grid h-screen place-items-center">
          <Card title="Login" className="flex flex-col">
            {/* <img src="../assets/images/logo_large.jpg" alt="logo" /> */}
            <Form onFinish={handleCreate} name="normal_login">
              <Form.Item>
                <label htmlFor="username">Username</label>
                <Input
                  type="text"
                  name="username"
                  value={3}
                  defaultValue="username123"
                />
              </Form.Item>
              <label htmlFor="password">Password</label>

              <Form.Item>
                <Input
                  type="password"
                  name="password"
                  value={2}
                  defaultValue="password123"
                />
                <div>
                  {error && <small className="text-danger">{error}</small>}
                </div>
              </Form.Item>
              <Form.Item>
                <Button htmlType="submit">Login</Button>
              </Form.Item>
            </Form>
          </Card>
        </div>
      </>
    );
  }
  return (
    <div className="container mt-3">
      <div className="grid h-screen place-items-center">
        <Card title="Logged In" className="flex flex-col">
          <p className="text-lg mb-3">Hi {username}. You are logged in!</p>
          <Button
            type="primary"
            className="ml-auto bg-info"
            onClick={redirectDashboard}
          >
            Enter Dashboard
          </Button>
        </Card>
      </div>
    </div>
  );
};

export default CreateOrganization;
