import React, { FC, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Input, Button, Form } from "antd";
import "./Login.css";
import { useMutation } from "react-query";
import { toast } from "react-toastify";
import LoadingSpinner from "../components/LoadingSpinner";
import { QueryErrors } from "../types/error-response-types";
import { Authentication } from "../api/api";

const ResetPassword: FC = () => {
  const [email, setEmail] = useState("");
  const [isEmailSent, setIsEmailSent] = useState(false);
  const navigate = useNavigate();

  const handleEmailChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(event.target.value);
  };

  const mutation = useMutation(() => Authentication.resetPassword(email), {
    onSuccess: () => {
      setIsEmailSent(true);
    },
    onError: (error: QueryErrors) => {
      if (error.response.status === 403) {
        toast.error("Please login again.");
        window.location.reload();
      } else {
        toast.error(
          Array.isArray(error.response.data.email)
            ? error.response.data.email[0]
            : error.response.data.email
        );
      }
    },
  });

  const handleResetPassword = () => {
    mutation.mutate();
  };

  return (
    <div className="grid h-screen place-items-center">
      {!isEmailSent ? (
        <div className="space-y-4">
          <Card
            title="Reset your Password"
            className="flex flex-col"
            style={{
              borderRadius: "0.5rem",
              borderWidth: "2px",
              borderColor: "#EAEAEB",
              borderStyle: "solid",
            }}
          >
            <Form onFinish={handleResetPassword} name="normal_login">
              <Form.Item>
                {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                <label htmlFor="email">Email</label>
                <Input
                  id="email"
                  type="text"
                  name="email"
                  value={email}
                  defaultValue="user123@email.com"
                  onChange={handleEmailChange}
                />
              </Form.Item>
              <Form.Item>
                <Button htmlType="submit">Reset Password</Button>
              </Form.Item>
            </Form>
          </Card>
          <div>
            <Button type="primary" onClick={() => navigate("/login")}>
              Login
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <p>
            An email was sent to {email}. Check your inbox and follow the
            instructions.
          </p>
          <div>
            <Button type="primary" onClick={() => navigate("/login")}>
              Back to Login
            </Button>
          </div>
        </div>
      )}
      {mutation.isLoading && <LoadingSpinner />}
    </div>
  );
};

export default ResetPassword;
