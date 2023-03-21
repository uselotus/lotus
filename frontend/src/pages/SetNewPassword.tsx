import React, { FC, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Authentication, instance } from "../api/api";
import { Card, Input, Button, Form } from "antd";
import "./Login.css";
import { useQueryClient, useMutation } from "react-query";
import { toast } from "react-toastify";
import Cookies from "universal-cookie";
import LoadingSpinner from "../components/LoadingSpinner";
import { QueryErrors } from "../types/error-response-types";

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
      Authentication.setNewPassword(data.token, data.userId, data.password),
    {
      onSuccess: (response) => {
        const { token, detail } = response;
        cookies.set("Token", token);
        instance.defaults.headers.common.Authorization = `Token ${token}`;
        setIsAuthenticated(true);
        queryClient.refetchQueries("session");
        redirectDashboard();
      },
      onError: (error: QueryErrors) => {
        // setError(error.message)

        toast.error(error.response.data.message);
      },
    }
  );

  const handleUpdatePassword = (event: React.FormEvent<FormElements>) => {
    if (token && userId) mutation.mutate({ token, userId, password });
  };

  if (!isAuthenticated) {
    return (
      <div className="grid h-screen place-items-center">
        <div className=" space-y-4">
          <Card
            title="Login"
            className="flex flex-col"
            style={{
              borderRadius: "0.5rem",
              borderWidth: "2px",
              borderColor: "#EAEAEB",
              borderStyle: "solid",
            }}
          >
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
                <Button htmlType="submit">Change Password</Button>
              </Form.Item>
            </Form>
          </Card>
          <div>
            <Button
              type="primary"
              onClick={() => navigate("/login")}
              disabled={(import.meta as any).env.VITE_NANGO_PK === "true"}
            >
              Login
            </Button>
          </div>
        </div>
        {mutation.isLoading && <LoadingSpinner />}
      </div>
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
