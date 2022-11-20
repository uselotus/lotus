import React, { FC, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Authentication } from "../api/api";
import { Card, Input, Button, Form } from "antd";
import "./Login.css";
import { useMutation } from "react-query";
import { toast } from "react-toastify";
import LoadingSpinner from "../components/LoadingSpinner";
import {LotusFilledButton, LotusOutlinedButton} from "../components/base/Button";

interface ResetPasswordForm extends HTMLFormControlsCollection {
  email: string;
}

interface FormElements extends HTMLFormElement {
  readonly elements: ResetPasswordForm;
}

const ResetPassword: FC = () => {
  const [email, setEmail] = useState("");
  const [isEmailSent, setIsEmailSent] = useState(false);
  const navigate = useNavigate();

  const handleEmailChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(event.target.value);
  };

  const mutation = useMutation(
    (data: { email: string }) => Authentication.resetPassword(email),
    {
      onSuccess: (response) => {
        setIsEmailSent(true);
      },
      onError: (error) => {
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
    }
  );

  const handleResetPassword = (event: React.FormEvent<FormElements>) => {
    mutation.mutate({ email });
  };

  return (
    <div className="grid h-screen place-items-center">
      {!isEmailSent ? (
        <div className="space-y-4">
          <Card title="Reset your Password" className="flex flex-col">
            <Form onFinish={handleResetPassword} name="normal_login">
              <Form.Item>
                <label htmlFor="email">Email</label>
                <Input
                  type="text"
                  name="email"
                  value={email}
                  defaultValue="user123@email.com"
                  onChange={handleEmailChange}
                />
              </Form.Item>
              <Form.Item>
                <LotusOutlinedButton text="Reset Password" htmlType="submit"/>
              </Form.Item>
            </Form>
          </Card>
          <div>
            <LotusFilledButton text="Login" onClick={() => navigate("/login")}/>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <p>
            An email was sent to {email}. Check your inbox and follow the
            instructions.
          </p>
          <div>
              <LotusFilledButton text="Back to Login" onClick={() => navigate("/login")}/>
          </div>
        </div>
      )}
      {mutation.isLoading && <LoadingSpinner />}
    </div>
  );
};

export default ResetPassword;
