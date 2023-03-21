import { Button, Steps } from "antd";
import React, { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-toastify";
import CreateOrganization, {
  Organizaton,
} from "../components/Registration/CreateOrganization";
import { Authentication } from "../api/api";
import { CreateOrgAccountType } from "../types/account-type";
import SignUp from "../components/Registration/SignUp";
import { QueryErrors } from "../types/error-response-types";
// import sjcl from "sjcl";

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
  organization_name: "",
  industry: "",
};

const Register: React.FC = () => {
  const [current, setCurrent] = useState(0);
  const [organization, setOrganization] = useState<Organizaton>(defaultOrg);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const inviteToken = searchParams.get("token");

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
        queryClient.invalidateQueries(["session"]);
        navigate("/login");
      },
      onError: (error: QueryErrors) => {
        toast.error(error.response.data.detail);
      },
    }
  );

  const handleSignUp = (user: {
    username: string;
    email: string;
    password: string;
  }) => {
    // const pwBitArray = sjcl.hash.sha256.hash(user.password);
    // const hashedPassword = sjcl.codec.hex.fromBits(pwBitArray);
    const register_object: CreateOrgAccountType = {
      organization_name: organization.organization_name,
      industry: organization.industry,
      email: user.email,
      password: user.password,
      username: user.username,
      invite_token: inviteToken,
    };

    mutation.mutate(register_object);
  };

  return (
    <div className="grid h-screen place-items-center gap-3">
      <div className=" space-y-4 place-items-center">
        {inviteToken ? (
          <SignUp onSubmit={handleSignUp} hasInvite />
        ) : (
          <>
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
          </>
        )}

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
