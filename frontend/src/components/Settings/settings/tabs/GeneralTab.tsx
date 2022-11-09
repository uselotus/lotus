import React, { FC, useState } from "react";
import { useQuery, useMutation } from "react-query";
import { useNavigate } from "react-router-dom";
import { Divider, Typography, Row, Col, Input, Button, Form, Tag } from "antd";
import { Organization } from "../../../../api/api";
import { toast } from "react-toastify";
import LoadingSpinner from "../../../LoadingSpinner";

interface InviteWithEmailForm extends HTMLFormControlsCollection {
  email: string;
}

interface FormElements extends HTMLFormElement {
  readonly elements: InviteWithEmailForm;
}

const GeneralTab: FC = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");

  // const {
  //   data: organization, // organization is the data returned from the query
  //   isLoading,
  //   isError,
  // } = useQuery(["organization"], () =>
  //   Organization.get().then((res) => {
  //     return res[0];
  //   })
  // );

  const handleEmailChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(event.target.value);
  };

  const mutation = useMutation(
    (data: { email: string }) => Organization.invite(email),
    {
      onSuccess: (response) => {
        toast.success("Invite sent");
      },
      onError: (error: any) => {
        if (error.response.data) {
          toast.error(
            Array.isArray(error.response.data.email)
              ? error.response.data.email[0]
              : error.response.data.email
          );
        } else {
          toast.error("Cannot send an invite now, try again later.");
        }
      },
    }
  );

  const handleSendInviteEmail = (event: React.FormEvent<FormElements>) => {
    mutation.mutate({ email });
  };

  return (
    <div>
      <Typography.Title level={2}>Organization Settings</Typography.Title>

      <Divider />

      {mutation.isLoading && <LoadingSpinner />}
    </div>
  );
};

export default GeneralTab;
