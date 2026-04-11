import { NextResponse } from "next/server";

/**
 * Meta Deauthorize Callback
 * Called when a user removes your app from their Instagram/Facebook account.
 * Meta sends a signed_request via POST form data.
 * https://developers.facebook.com/docs/apps/delete-data
 */
export async function POST(): Promise<NextResponse> {
  // For a single-owner posting app there are no user records to delete.
  // Acknowledging with 200 satisfies Meta's requirement.
  return NextResponse.json({ success: true }, { status: 200 });
}
