/* eslint-disable jsx-a11y/label-has-associated-control */
import React, { useState } from "react";
import { Card, Input, Button, Form, Select } from "antd";

export interface Organizaton {
  organization_name: string;
  industry: string;
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

function CreateOrganization({
  onSave,
}: {
  onSave: (org: Organizaton) => void;
}) {
  const [companyName, setCompanyName] = useState("");
  const [industry, setIndustry] = useState("");

  const handleIndustrySelect = (value: string) => {
    setIndustry(value);
  };

  const handleNameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setCompanyName(event.target.value);
  };

  const handleOrganizationSubmit = () => {
    onSave({ organization_name: companyName, industry });
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
            <label htmlFor="organization_name">Organization Name</label>
            <Input
              type="text"
              name="organization_name"
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
}

export default CreateOrganization;
