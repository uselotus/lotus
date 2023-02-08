/* eslint-disable jsx-a11y/label-has-associated-control */
/* eslint-disable camelcase */
import { Button, Card, Form, Input } from "antd";
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "react-query";
import Cookies from "universal-cookie";
import { toast } from "react-toastify";
import { Organizaton } from "../components/Registration/CreateOrganization";
import { Authentication, instance } from "../api/api";
import LoadingSpinner from "../components/LoadingSpinner";
import { ErrorResponseMessage } from "../types/error-response-types";

const cookies = new Cookies();

export interface DemoSignupProps {
  username: string;
  email: string;
  password: string;
  organization_name: string;
}

const defaultOrg: Organizaton = {
  organization_name: "",
  industry: "",
};

const DemoSignup: React.FC = () => {
  const [organization] = useState<Organizaton>(defaultOrg);
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [form] = Form.useForm();
  const [isDesktop, setIsDesktop] = useState(true);

  useEffect(() => {
    const { userAgent } = navigator;

    if (/iPad|iPhone|iPod|Android/.test(userAgent)) {
      setIsDesktop(false);
    }
  }, []);
  const [timeOutId, setTimeOutId] = useState<NodeJS.Timeout | undefined>();

  const queryClient = useQueryClient();

  const mutation = useMutation(
    (register: DemoSignupProps) => Authentication.registerDemo(register),
    {
      onSuccess: (response) => {
        const { token } = response;
        cookies.set("Token", token);
        instance.defaults.headers.common.Authorization = `Token ${token}`;
        queryClient.invalidateQueries("session");
      },
      onError: (error: ErrorResponseMessage) => {
        toast.error(error.response.data.detail, {
          position: "top-center",
        });
        navigate("/login");
      },
    }
  );

  const handleUserNameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setUsername(event.target.value);
  };

  const handlePasswordChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setPassword(event.target.value);
  };
  const handleEmailChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(event.target.value);
  };

  const handleSignUp = () => {
    // const pwBitArray = sjcl.hash.sha256.hash(user.password);
    // const hashedPassword = sjcl.codec.hex.fromBits(pwBitArray);
    form.validateFields().then(() => {
      const register_object: DemoSignupProps = {
        organization_name: organization.organization_name,
        email,
        password,
        username,
      };

      mutation.mutate(register_object);
    });
  };

  useEffect(() => {
    if (mutation.isLoading) {
      setTimeOutId(setTimeout(() => navigate("/login"), 15000));
    }

    return () => {
      clearTimeout(timeOutId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mutation.isLoading]);

  return (
    <div>
      {isDesktop ? (
        <div className="grid h-screen place-items-center">
          {mutation.isLoading ? (
            <div>
              <h1>Creating your demo account...</h1>
              <LoadingSpinner />
            </div>
          ) : (
            <div className="space-y-4 w-4/12">
              <div className="">
                <div>
                  <Card
                    title="Create Lotus Demo Account"
                    className="flex flex-col"
                    style={{
                      borderRadius: "0.5rem",
                      borderWidth: "2px",
                      borderColor: "#EAEAEB",
                      borderStyle: "solid",
                    }}
                  >
                    {/* <img src="../assets/images/logo_large.jpg" alt="logo" /> */}
                    <Form onFinish={handleSignUp} name="create_organization">
                      <Form.Item>
                        {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                        <label htmlFor="username">Username</label>
                        <Input
                          type="text"
                          name="organization_name"
                          value={username}
                          defaultValue="username123"
                          onChange={handleUserNameChange}
                        />
                      </Form.Item>
                      <Form.Item
                        rules={[
                          {
                            required: true,
                            type: "email",
                            message: "The input is not valid E-mail!",
                          },
                        ]}
                      >
                        {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                        <label htmlFor="username">Email</label>
                        <Input
                          type="email"
                          name="email"
                          value={email}
                          defaultValue="elon@musk.com"
                          onChange={handleEmailChange}
                        />
                      </Form.Item>
                      <Form.Item>
                        <label htmlFor="password">Password</label>
                        <Input
                          type="password"
                          name="password"
                          value={password}
                          defaultValue="password123"
                          onChange={handlePasswordChange}
                        />
                      </Form.Item>

                      <Form.Item className="justify-self-center	">
                        <Button htmlType="submit">Continue to Demo</Button>
                      </Form.Item>
                    </Form>
                  </Card>
                </div>
              </div>

              <div className="">
                <Button
                  type="primary"
                  className="w-full"
                  onClick={() => navigate("/login")}
                >
                  Login to Your Demo Instead
                </Button>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="grid h-screen place-items-center">
          Use a computer please
        </div>
      )}
    </div>
  );
};

export default DemoSignup;
