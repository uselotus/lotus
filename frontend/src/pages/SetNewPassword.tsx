import React, { FC, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Authentication } from "../api/api";
import { Card, Input, Button, Form, Modal } from "antd";
import "./Login.css";
import { useQueryClient, useMutation } from "react-query";
import { toast } from "react-toastify";
import LoadingSpinner from "../components/LoadingSpinner";
import { instance } from "../api/api";
import Cookies from "universal-cookie";
import {LotusFilledButton, LotusOutlinedButton} from "../components/base/Button";

const cookies = new Cookies();

interface LoginForm extends HTMLFormControlsCollection {
  username: string;
  password: string;
}

interface FormElements extends HTMLFormElement {
  readonly elements: LoginForm;
}

const SetNewPassword: FC = () => {
  const [searchParams] = useSearchParams();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const queryClient = useQueryClient();

  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const navigate = useNavigate();

  const userId = searchParams.get("userId");
  const token = searchParams.get("token");

  const handlePasswordChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setPassword(event.target.value);
  };

  const redirectDashboard = () => {
    navigate("/dashboard");
  };

  const mutation = useMutation(
    (data: { userId: string; token: string; password: string }) =>
      Authentication.setNewPassword(token, userId, password),
    {
      onSuccess: (response) => {
        const { token, detail } = response;
        cookies.set("Token", token);
        instance.defaults.headers.common["Authorization"] = `Token ${token}`;
        setIsAuthenticated(true);
        queryClient.refetchQueries("session");
        redirectDashboard();
      },
      onError: (error) => {
        // setError(error.message)
        toast.error(error.response.data.message);
      },
    }
  );

  const handleUpdatePassword = (event: React.FormEvent<FormElements>) => {
    mutation.mutate({ token, userId, password });
  };

  if (!isAuthenticated) {
    return (
      <>
        <div className="grid h-screen place-items-center">
          <div className=" space-y-4">
            <Card title="Login" className="flex flex-col">
              <Form onFinish={handleUpdatePassword} name="normal_login">
                <label htmlFor="password">New Password</label>
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
                  <LotusOutlinedButton text="Change Password" htmlType="submit"/>
                </Form.Item>
              </Form>
            </Card>
            <div>
              <LotusFilledButton text="Login" onClick={() => navigate("/login")}/>
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

export default SetNewPassword;
