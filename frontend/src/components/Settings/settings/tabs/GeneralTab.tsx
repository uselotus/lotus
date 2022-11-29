// @ts-ignore
import React, { FC, useState } from "react";
import {useMutation, useQuery} from "react-query";
import { useNavigate } from "react-router-dom";
import { Divider, Typography } from "antd";
import {Organization} from "../../../../api/api";
import { toast } from "react-toastify";
import LoadingSpinner from "../../../LoadingSpinner";
import PricingUnitDropDown from "../../../PricingUnitDropDown";

interface InviteWithEmailForm extends HTMLFormControlsCollection {
  email: string;
}

interface FormElements extends HTMLFormElement {
  readonly elements: InviteWithEmailForm;
}

const GeneralTab: FC = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");

  const {
    data,
    isLoading,
    isError,
  } = useQuery(["organization"], () =>
    Organization.get().then((res) => {
      return res[0];
    })
  );

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

   const updateOrg = useMutation(
    (obj: { org_id: string; default_currency_code: string } ) => Organization.updateOrganization(obj.org_id, obj.default_currency_code),
    {
      onSuccess: () => {
        toast.success("Successfully Updated Default Currency", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onError: () => {
        toast.error("Failed to Update Default Currency", {
          position: toast.POSITION.TOP_CENTER,
        });
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
        <p>
            <b>Default Organization Currency:</b> { data?.default_currency ? (
            <PricingUnitDropDown defaultValue={data?.default_currency?.code }
                                 setCurrentCurrency={value => updateOrg.mutate({
                                     org_id: data.organization_id,
                                     default_currency_code: value
                                 })}/>
        ) : "N/A"}
        </p>
    </div>
  );
};

export default GeneralTab;
