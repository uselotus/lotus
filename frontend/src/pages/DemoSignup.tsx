import { Button, message, Card, Form, Input } from "antd";
import React, { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Organizaton } from "../components/Registration/CreateOrganization";
import { Authentication } from "../api/api";
import { useMutation, useQueryClient } from "react-query";
import LoadingSpinner from "../components/LoadingSpinner";
import { instance } from "../api/api";
import Cookies from "universal-cookie";
import { toast } from "react-toastify";

const cookies = new Cookies();

// import sjcl from "sjcl";

export interface DemoSignupProps {
  username: string;
  email: string;
  password: string;
  company_name: string;
}

const defaultOrg: Organizaton = {
  company_name: "",
  industry: "",
};

const DemoSignup: React.FC = () => {
  const [current, setCurrent] = useState(0);
  const [organization, setOrganization] = useState<Organizaton>(defaultOrg);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [form] = Form.useForm();

  const queryClient = useQueryClient();
  const next = () => {
    setCurrent(current + 1);
  };

  const prev = () => {
    setCurrent(current - 1);
  };

  const handleCreateOrganization = (org: Organizaton) => {
    setOrganization(org);
    next();
  };

  const mutation = useMutation(
    (register: DemoSignupProps) => Authentication.registerDemo(register),
    {
      onSuccess: (response) => {
        const { token, detail } = response;
        cookies.set("Token", token);
        instance.defaults.headers.common["Authorization"] = `Token ${token}`;
        queryClient.invalidateQueries("session");
      },
      onError: (error: any) => {
        toast.error(error.response.data.detail, {
          position: "top-center",
        });
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
        company_name: organization.company_name,
        email: email,
        password: password,
        username: username,
      };

      mutation.mutate(register_object);
    });
  };

  return (
    <div className="grid h-screen place-items-center">
      {mutation.isLoading ? (
        <div>
          <h1>Creating your demo account...</h1>
          <LoadingSpinner />
        </div>
      ) : (
        <div className="space-y-4 w-2/12">
          <div className="">
            <div>
              <Card
                title={"Create Lotus Demo Account"}
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
                    <label htmlFor="username">Username</label>
                    <Input
                      type="text"
                      name="company_name"
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
  );
};

export default DemoSignup;
