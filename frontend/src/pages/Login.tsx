import React, { FC, useState } from "react";
import { useNavigate, Link, useLocation } from "react-router-dom";
import { Authentication, instance } from "../api/api";
import { Card, Input, Button, Form } from "antd";
import "./Login.css";
import { useQueryClient, useMutation } from "@tanstack/react-query";
import { toast } from "react-toastify";
import Cookies from "universal-cookie";
import posthog from "posthog-js";
import LoadingSpinner from "../components/LoadingSpinner";
import { QueryErrors } from "../types/error-response-types";
import useGlobalStore from "../stores/useGlobalstore";
import Tooltip from "../components/base/Tooltip/Tooltip";
import Avatar from "../components/base/Avatar/Avatar";
import Dropdown from "../components/base/Dropdown/Dropdown";

const cookies = new Cookies();

interface LoginForm extends HTMLFormControlsCollection {
  username: string;
  password: string;
}

interface FormElements extends HTMLFormElement {
  readonly elements: LoginForm;
}
interface LocationState {
  redirectTo?: string;
}
interface LoginProps {
  username?: string;
  password?: string;
}

const Login: FC<LoginProps> = (props) => {
  const [username, setUsername] = useState(props.username || "");
  const [password, setPassword] = useState(props.password || "");
  const [error, setError] = useState("");
  const setUsernameToStore = useGlobalStore((state) => state.setUsername);
  const queryClient = useQueryClient();
  const location = useLocation();

  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const navigate = useNavigate();

  const handlePasswordChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setPassword(event.target.value);
  };

  const handleUserNameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setUsername(event.target.value);
  };

  const redirectAfterLogin = () => {
    navigate((location.state as LocationState).redirectTo!);
  };

  const isDemo = (import.meta as any).env.VITE_IS_DEMO === "true";

  const mutation = useMutation(
    (data: { username: string; password: string }) =>
      isDemo
        ? Authentication.demo_login(username, password)
        : Authentication.login(username, password),

    {
      onSuccess: (response) => {
        setIsAuthenticated(true);
        const { token, detail, user } = response;
        setUsernameToStore(user.username);
        if (import.meta.env.VITE_API_URL === "https://api.uselotus.io/") {
          posthog.group("company", user.organization_id, {
            organization_name: user.organization_name,
          });
          posthog.identify(
            user.email, // distinct_id, required
            { organization_id: user.organization_id }, // $set, optional
            { username: user.username } // $set_once, optional
          );
        }

        cookies.set("Token", token);
        instance.defaults.headers.common.Authorization = `Token ${token}`;
        queryClient.refetchQueries(["session"]);
        redirectAfterLogin();
      },
      onError: (error: QueryErrors) => {
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
    // const pwBitArray = sjcl.hash.sha256.hash(password);
    // const hashedPassword = sjcl.codec.hex.fromBits(pwBitArray);
    mutation.mutate({ username, password });
  };

  if (!isAuthenticated) {
    return (
      <div className="grid h-screen place-items-center">
        <div className="space-y-4">
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
            {/* <img src="../assets/images/logo_large.jpg" alt="logo" /> */}
            <Form onFinish={handleLogin} name="normal_login">
              <Form.Item>
                <label htmlFor="username">Username or Email</label>
                <Input
                  type="text"
                  name="username"
                  id="username"
                  value={username}
                  defaultValue="username123"
                  onChange={handleUserNameChange}
                />
              </Form.Item>
              <label htmlFor="password">Password</label>

              <Form.Item>
                <Input
                  type="password"
                  id="password"
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
              <Link
                to="/reset-password"
                className=" text-darkgold hover:text-black"
              >
                Forgot Password?
              </Link>
            </Form>
          </Card>
          {(import.meta.env.VITE_API_URL !== "https://api.uselotus.io/" ||
            import.meta.env.IS_DEMO == "true") && (
            <div>
              <Button
                type="primary"
                className="w-full"
                onClick={() => navigate("/register")}
              >
                Sign Up
              </Button>
            </div>
          )}
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

export default Login;
