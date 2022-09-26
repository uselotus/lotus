import React, { FC, useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Authentication } from "../api/api";
import { Card, Input, Button, Form, Modal } from "antd";
import "./Login.css";
import { useQueryClient, useMutation } from "react-query";
import { toast } from "react-toastify";
import LoadingSpinner from "../components/LoadingSpinner";

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
  const queryClient = useQueryClient();

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

  const mutation = useMutation(
    (data: { username: string; password: string }) =>
      Authentication.login(username, password),
    {
      onSuccess: () => {
        setIsAuthenticated(true);
        queryClient.refetchQueries("session");
        redirectDashboard();
      },
      onError: (error) => {
        // setError(error.message);
        if (error.response.status === 403) {
          toast.error("Please login again.");
          window.location.reload();
        } else {
          toast.error(error.response.data.detail);
        }
      },
    }
  );

  const handleLogin = (event: React.FormEvent<FormElements>) => {
    mutation.mutate({ username, password });
  };

  if (!isAuthenticated) {
    return (
      <>
        <div className="grid h-screen place-items-center">
          <div className=" space-y-4">
            <Card title="Login" className="flex flex-col">
              {/* <img src="../assets/images/logo_large.jpg" alt="logo" /> */}
              <Form onFinish={handleLogin} name="normal_login">
                <Form.Item>
                  <label htmlFor="username">Username</label>
                  <Input
                    type="text"
                    name="username"
                    value={username}
                    defaultValue="username123"
                    onChange={handleUserNameChange}
                  />
                </Form.Item>
                <label htmlFor="password">Password</label>

                <Form.Item>
                  <Input
                    type="password"
                    name="password"
                    value={password}
                    defaultValue="password123"
                    onChange={handlePasswordChange}
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
            <div>
              <Button
                type="primary"
                className="ml-auto bg-info"
                onClick={() => navigate("/register")}
              >
                Sign Up
              </Button>
            </div>
          </div>
          {mutation.isLoading && <LoadingSpinner />}
        </div>
      </>
    );
  }

  return (
    <div className="container mt-3">
      <div className="grid h-screen place-items-center">
        <LoadingSpinner />
      </div>
    </div>
  );
};

export default Login;
