import { Button, message, Steps } from "antd";
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import CreateOrganization from "../components/Registration/CreateOrganization";
import { Organizaton } from "../components/Registration/CreateOrganization";
import { Authentication } from "../api/api";
import { useMutation, useQueryClient } from "react-query";
import { CreateOrgAccountType } from "../types/account-type";
import SignUp from "../components/Registration/SignUp";

const { Step } = Steps;

const steps = [
  {
    title: "Create Organization",
    content: "organization",
  },
  {
    title: "Sign Up",
    content: "signup",
  },
];

const defaultOrg: Organizaton = {
  company_name: "",
  industry: "",
};

const Register: React.FC = () => {
  const [current, setCurrent] = useState(0);
  const [organization, setOrganization] = useState<Organizaton>(defaultOrg);
  const navigate = useNavigate();

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
    (register: CreateOrgAccountType) => Authentication.registerCreate(register),
    {
      onSuccess: () => {
        queryClient.invalidateQueries("session");
        navigate("/dashboard");
      },
    }
  );

  const handleSignUp = (user: {
    username: string;
    email: string;
    password: string;
  }) => {
    const register_object: CreateOrgAccountType = {
      company_name: organization.company_name,
      industry: organization.industry,
      email: user.email,
      password: user.password,
      username: user.username,
    };

    mutation.mutate(register_object);
  };

  return (
    <div className="grid h-screen place-items-center gap-3">
      <div className=" space-y-4 place-items-center">
        <Steps current={current}>
          {steps.map((item) => (
            <Step key={item.title} title={item.title} />
          ))}
        </Steps>
        <div className="steps-content">
          {" "}
          {current === 0 ? (
            <CreateOrganization onSave={handleCreateOrganization} />
          ) : (
            <SignUp onSubmit={handleSignUp} />
          )}
        </div>
        <div className="steps-action">
          <Button
            type="primary"
            className="ml-auto bg-info"
            onClick={() => navigate("/login")}
          >
            Log In Instead
          </Button>
        </div>
      </div>
    </div>
  );
};

export default Register;
