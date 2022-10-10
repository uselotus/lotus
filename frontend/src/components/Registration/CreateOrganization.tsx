import React, { FC, useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Card, Input, Button, Form, Select } from "antd";
import { useQueryClient } from "react-query";

interface LoginForm extends HTMLFormControlsCollection {
  username: string;
  password: string;
}

export interface Organizaton {
  company_name: string;
  industry: string;
}

interface FormElements extends HTMLFormElement {
  readonly elements: LoginForm;
}

const industries = [
  { label: "AI", value: "ai" },
  { label: "Health Tech", value: "healthtech" },
  { label: "Fintech", value: "fintech" },
  { label: "Ecommerce", value: "ecommerce" },
  { label: "Platform", value: "platform" },
  { label: "Dev Tools", value: "devtools" },
  { label: "Cloud Infra", value: "cloudinfrustructure" },
  { label: "Data Management", value: "datamanagement" },
  { label: "Other", value: "other" },
];

const CreateOrganization = (props: { onSave: (org: Organizaton) => void }) => {
  const [companyName, setCompanyName] = useState("");
  const [industry, setIndustry] = useState("");
  const [error, setError] = useState("");
  const queryClient = useQueryClient();

  const navigate = useNavigate();

  const handleIndustrySelect = (value: string) => {
    setIndustry(value);
  };

  const handleNameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setCompanyName(event.target.value);
  };

  const handleOrganizationSubmit = (event: React.FormEvent<FormElements>) => {
    props.onSave({ company_name: companyName, industry });
  };

  return (
    <div>
      <Card title="Create Organization" className="flex flex-col">
        {/* <img src="../assets/images/logo_large.jpg" alt="logo" /> */}
        <Form onFinish={handleOrganizationSubmit} name="create_organization">
          <Form.Item
            rules={[
              {
                required: true,
                message: "The name of your company",
              },
            ]}
          >
            <label htmlFor="company_name">Organization Name</label>
            <Input
              type="text"
              name="company_name"
              value={companyName}
              defaultValue="username123"
              onChange={handleNameChange}
            />
          </Form.Item>
          <label htmlFor="password">Industry</label>

          <Form.Item
            rules={[
              {
                required: true,
                message: "Select the most relevant industry",
              },
            ]}
          >
            <Select onSelect={handleIndustrySelect} options={industries} />
          </Form.Item>
          <Form.Item>
            <Button htmlType="submit">Next</Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default CreateOrganization;
